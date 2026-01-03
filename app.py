from flask import Flask, request, jsonify
import acoustid
import musicbrainzngs
import os
import tempfile

app = Flask(__name__)

# AYARLAR
API_KEY = '3OoK8s537Q' # Yeni ve geçerli API Anahtarı
musicbrainzngs.set_useragent("MyMusicApp", "0.1", "student@gazi.edu.tr")

@app.route('/', methods=['GET'])
def home():
    return "Otonom Müzik Sunucusu Çalışıyor! 🎵"

@app.route('/identify', methods=['POST'])
def identify():
    if 'file' not in request.files:
        return jsonify({"error": "Dosya yok"}), 400
    
    file = request.files['file']
    
    # Geçici dosya oluştur (Server'a gelen dosyayı kaydet)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp:
        file.save(temp.name)
        temp_path = temp.name

    try:
        # 1. Parmak izi ve API Sorgusu
        # Render (Linux) için yerel binary'yi kullanıyoruz
        fpcalc_path = os.path.join(os.path.dirname(__file__), "fpcalc_linux" if os.name != 'nt' else "fpcalc.exe")
        
        # Eğer yerel binary varsa çevresel değişken olarak ayarla
        if os.path.exists(fpcalc_path):
            os.environ['FPCALC'] = fpcalc_path
            # Linux'ta çalışma izni ver (her ihtimale karşı)
            if os.name != 'nt':
                os.chmod(fpcalc_path, 0o755)

        duration, fingerprint = acoustid.fingerprint_file(temp_path)

        results = acoustid.lookup(API_KEY, fingerprint, duration, meta=['recordings', 'releases'])
        
        best_match = None
        if 'results' in results:
            for result in results['results']:
                if result['score'] > 0.4:
                    best_match = result
                    break
        
        if best_match:
            recordings = best_match.get('recordings', [])
            if not recordings:
                 return jsonify({"success": False, "message": "Kayıt detayı bulunamadı"}), 404
            
            recording = recordings[0]
            rec_id = recording.get('id')
            title = recording.get('title', "Bilinmeyen Başlık")
            
            # Artist safe access
            artists = recording.get('artists', [])
            artist = "Bilinmiyor"
            if artists and len(artists) > 0:
                artist = artists[0].get('name', "Bilinmiyor")
            
            album_name = None
            release_id = None

            # 1. Aşama: AcoustID içinden Release ID çekmeye çalış
            releases = best_match.get('releases', [])
            if releases:
                album_name = releases[0].get('title')
                release_id = releases[0].get('id')
            elif 'releases' in recording:
                rec_releases = recording.get('releases', [])
                if rec_releases:
                    album_name = rec_releases[0].get('title')
                    release_id = rec_releases[0].get('id')

            # 2. Aşama: Eğer hala yoksa, MusicBrainz'e derinlemesine sor
            if not release_id and rec_id:
                try:
                    mb_res = musicbrainzngs.get_recording_by_id(rec_id, includes=["releases"])
                    if 'recording' in mb_res:
                        mb_rec = mb_res['recording']
                        if 'release-list' in mb_rec and mb_rec['release-list']:
                            first_release = mb_rec['release-list'][0]
                            album_name = first_release.get('title')
                            release_id = first_release.get('id')
                except Exception as mb_err:
                    print(f"B planı (MB Lookup) başarısız: {mb_err}")

            return jsonify({
                "success": True,
                "mbid": rec_id,
                "release_id": release_id,
                "title": title,
                "artist": artist,
                "album": album_name
            })
        else:
            return jsonify({"success": False, "message": "Eşleşme bulunamadı"}), 404

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        # Temizlik: Geçici dosyayı sil
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == '__main__':
    app.run(debug=True)