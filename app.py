from flask import Flask, request, jsonify
import acoustid
import musicbrainzngs
import os
import tempfile

app = Flask(__name__)

# AYARLAR
API_KEY = 'T5f0Zrf0Lu' # Senin Keyin
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
        for result in results.get('results', []):
            if result['score'] > 0.4:  # Mozart gibi parçalar için eşiği düşürdük
                best_match = result
                break
        
        if best_match:
            rec_id = best_match['recordings'][0]['id']
            title = best_match['recordings'][0]['title']
            
            # MusicBrainz detay sorgusu (İstersen ekle)
            return jsonify({
                "success": True,
                "mbid": rec_id,
                "title": title,
                "artist": best_match['recordings'][0]['artists'][0]['name'] if 'artists' in best_match['recordings'][0] else "Bilinmiyor"
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