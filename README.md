DicBackup - Web Tabanlı Sunucu Yönetim Paneli

DicBackup, Linux sunucular için yedekleme, senkronizasyon ve dosya transferi işlemlerini modern ve kullanıcı dostu bir web arayüzü üzerinden yönetmenizi sağlayan bir Flask uygulamasıdır.
Karmaşık komut satırı işlemlerini, herkesin kullanabileceği şık bir panele taşır.
✨ Özellikler

Bu proje, bir sunucu yöneticisinin ihtiyaç duyabileceği güçlü araçları tek bir arayüzde birleştirir:


   - 📁 Manuel Yedekleme: İstediğiniz dosya veya klasörü anında .tar.gz formatında arşivleyin.
    
   - 💿 Disk İmajı: dd komutunu kullanarak bir diskin veya bölümün tam imaj yedeğini alın.
    
   - 🔄 Dosya Senkronizasyonu: rsync kullanarak iki klasör arasındaki veriyi (tek yönlü) eşitleyin.
    
  ⏰ Otomatik Yedekleme:
    
  -   Yedekleme görevlerini günlük, haftalık veya aylık olarak planlayın.
        
  -   Her plan için yedeklemenin tam olarak saat kaçta başlayacağını belirleyin.
        
  -   Tüm planlar, uygulama yeniden başlasa bile kaybolmayacak şekilde bir veritabanında saklanır.
        
  - ♻️ Yedek Rotasyonu: Her yedekleme hedefi için otomatik olarak sadece en son 2 yedeği tutar, en eskisini silerek disk alanından tasarruf sağlar.
    
  🌐 Gelişmiş FTP İstemcisi:
    
  -  FileZilla benzeri çift panelli arayüz (Yerel Site / Uzak Site).
        
  -  Sürükle-bırak ile kolayca dosya ve klasör yükleme/indirme.
        
  -  Uzak sunucuda yeni klasör oluşturma.
        
  -  Klasörler arasında çift tıklayarak gezinme.
        
  🖥️ Sistem Bilgisi: Sunucuya bağlı diskleri ve boş alanlarını listeleme.
    
  📝 Loglama: Tüm yedekleme, silme ve hata işlemleri ~/backups/backup.log dosyasına kaydedilir.
    
    
🚀 Kurulum ve Çalıştırma

Projeyi kendi sunucunuzda çalıştırmak için aşağıdaki adımları izleyin.
Gereksinimler

  - Python 3.8+ ve pip

  - python3-venv paketi (sudo apt install python3.12-venv gibi)

  - tar, rsync, dd, lsblk komutlarının sistemde yüklü olması (çoğu Linux dağıtımında varsayılan olarak gelir).

Adım Adım Kurulum

  **Projeyi Klonlayın:**

    git clone https://github.com/erogluyusuf/dicbackup.git
    cd dicbackup

  **Sanal Ortam Oluşturun ve Aktif Edin:**

    python3 -m venv venv
    source venv/bin/activate

  ** Gerekli Python Paketlerini Yükleyin:**

    pip install -r requirements.txt


  **Uygulamayı Çalıştırın:**

    python3 app.py

   **Arayüze Erişin:**
   
   Web tarayıcınızı açın ve ''' http://<sunucu_ipsi>:5000 ''' adresine gidin. Artık paneli kullanmaya başlayabilirsiniz!
   
🛠️ Kullanılan Teknolojiler

  - Backend: Python / Flask

 - Zamanlama: APScheduler

 - Frontend: HTML5, CSS3, Vanilla JavaScript

 - Sistem Araçları: tar, dd, rsync, lsblk, psutil

 - Veritabanı (Zamanlayıcı için): SQLite

🖼️ Ekran Görüntüleri

Yedekleme Paneli:
[Yedekleme Paneli Görüntüsü]

FTP İstemcisi:
[FTP İstemcisi Görüntüsü]
📄 Lisans

Bu proje MIT Lisansı altında lisanslanmıştır. Detaylar için LICENSE dosyasına bakınız.
