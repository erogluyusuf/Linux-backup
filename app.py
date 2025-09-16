import os
import subprocess
import datetime
import re
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, session
import psutil
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
import ftplib
import getpass
app = Flask(__name__)
app.secret_key = "b7f3d45c5d8a9a6e7c2f8a4e1b29e7f1c3d8f5a7e2c4b1f9d8c2a7f3b6d9e5c1"

# ==============
APP_USER = getpass.getuser() 
BACKUP_ROOT_DIR = f'/home/{APP_USER}/backups'
os.makedirs(BACKUP_ROOT_DIR, exist_ok=True)

# Zamanlayıcı veritabanı ayarları
jobstores = { 'default': SQLAlchemyJobStore(url=f'sqlite:///{os.path.join(BACKUP_ROOT_DIR, "jobs.sqlite")}') }
scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start()

# --- FTP BAĞLANTI YARDIMCISI ---
def _get_ftp_connection_from_session():
    if 'ftp_details' not in session: return None, "FTP bağlantı bilgileri bulunamadı."
    details = session['ftp_details']
    try:
        ftp = ftplib.FTP(); ftp.connect(details['host'], int(details['port']))
        ftp.login(details['user'], details['pass']); ftp.set_pasv(True)
        return ftp, None
    except ftplib.all_errors as e: return None, str(e)

# --- KLASÖR TRANSFERİ İÇİN YARDIMCI FONKSİYONLAR ---
def ftp_upload_folder_recursive(ftp, local_path, remote_path):
    for item in os.listdir(local_path):
        local_item_path = os.path.join(local_path, item)
        remote_item_path = os.path.join(remote_path, item).replace("\\", "/")
        if os.path.isdir(local_item_path):
            try: ftp.mkd(remote_item_path)
            except ftplib.all_errors as e: log_message(f"FTP klasör oluşturulamadı (zaten var olabilir): {remote_item_path} - {e}")
            ftp_upload_folder_recursive(ftp, local_item_path, remote_item_path)
        else:
            with open(local_item_path, 'rb') as f: ftp.storbinary(f'STOR {remote_item_path}', f)

def ftp_download_folder_recursive(ftp, remote_path, local_path):
    os.makedirs(local_path, exist_ok=True)
    for item_data in ftp.mlsd(path=remote_path):
        name, meta = item_data
        if name in ('.', '..'): continue
        remote_item_path = os.path.join(remote_path, name).replace("\\", "/")
        local_item_path = os.path.join(local_path, name)
        if meta.get('type') == 'dir':
            ftp_download_folder_recursive(ftp, remote_item_path, local_item_path)
        else:
            with open(local_item_path, 'wb') as f: ftp.retrbinary(f'RETR {remote_item_path}', f.write)

# --- Yedekleme Mantığı Fonksiyonu ---
def perform_backup_job(source, dest_root):
    log_message(f"Yedekleme işi başladı: {source} -> {dest_root}")
    try:
        if not source or not os.path.exists(source):
            log_message(f"HATA: Yedekleme için kaynak dizin '{source}' bulunamadı!"); return
        backup_id = re.sub(r'[^a-zA-Z0-9]', '_', source.strip('/')); dest_path = os.path.join(dest_root, backup_id)
        os.makedirs(dest_path, exist_ok=True)
        existing_backups = sorted([f for f in os.listdir(dest_path) if f.endswith('.tar.gz')])
        while len(existing_backups) >= 2:
            oldest_backup = existing_backups.pop(0)
            os.remove(os.path.join(dest_path, oldest_backup)); log_message(f"Eski yedek silindi (rotasyon): {oldest_backup}")
        date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S"); filename = f"backup_{date}.tar.gz"
        full_path = os.path.join(dest_path, filename)
        parent_dir = os.path.dirname(source); target_name = os.path.basename(source)
        cmd = f"tar -czf {full_path} -C {parent_dir} {target_name}"
        subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        log_message(f"YEDEKLEME TAMAMLANDI: {full_path}")
    except Exception as e:
        log_message(f"YEDEKLEME HATASI ({source}): {e}")

# --- Yardımcı Fonksiyonlar ---
def get_mounted_drives():
    drives = [];
    try:
        for p in psutil.disk_partitions():
            if 'loop' not in p.device and p.mountpoint:
                drives.append({'path': p.mountpoint, 'total': f"{psutil.disk_usage(p.mountpoint).total / (1024**3):.2f} GB", 'free': f"{psutil.disk_usage(p.mountpoint).free / (1024**3):.2f} GB"})
    except Exception as e: log_message(f"Disk bilgileri alınamadı: {e}")
    return drives

def get_block_devices():
    devices = []
    try:
        result = subprocess.run(['lsblk', '-dnpo', 'NAME,SIZE'], capture_output=True, text=True, check=True)
        for line in result.stdout.strip().split('\n'):
            parts = re.split(r'\s+', line, 1)
            if len(parts) == 2: devices.append({'name': parts[0], 'size': parts[1]})
    except Exception as e: log_message(f"Blok aygıtları listelenemedi: {e}")
    return devices

def get_existing_backups():
    all_backups = []
    if not os.path.exists(BACKUP_ROOT_DIR): return all_backups
    for backup_id in os.listdir(BACKUP_ROOT_DIR):
        id_path = os.path.join(BACKUP_ROOT_DIR, backup_id)
        if os.path.isdir(id_path):
            for filename in os.listdir(id_path):
                if filename.endswith((".tar.gz", ".img.gz")):
                    file_path = os.path.join(id_path, filename)
                    try:
                        stat = os.stat(file_path)
                        all_backups.append({'id': backup_id, 'name': filename, 'size': f"{stat.st_size / (1024**2):.2f} MB", 'date': datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')})
                    except FileNotFoundError: continue
    all_backups.sort(key=lambda x: x['date'], reverse=True)
    return all_backups

def log_message(message):
    log_file = os.path.join(BACKUP_ROOT_DIR, 'backup.log')
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_file, 'a') as f: f.write(f"[{timestamp}] {message}\n")

# --- ANA SAYFA VE YEDEKLEME ROTALARI ---
@app.route("/")
def index():
    drives = get_mounted_drives(); block_devices = get_block_devices(); backups = get_existing_backups()
    scheduled_jobs = []
    try:
        for job in scheduler.get_jobs():
            scheduled_jobs.append({'id': job.id, 'name': job.name, 'trigger': str(job.trigger), 'next_run': job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else 'Yok'})
    except Exception as e: log_message(f"Zamanlanmış görevler okunurken hata: {e}")
    return render_template("index.html", drives=drives, block_devices=block_devices, backups=backups, scheduled_jobs=scheduled_jobs)

@app.route("/backup-file", methods=["POST"])
def backup_file():
    source = request.form.get("source"); dest_root = request.form.get("destination") or BACKUP_ROOT_DIR
    perform_backup_job(source, dest_root); flash(f"Manuel yedekleme işi '{source}' için başarıyla tamamlandı.", "success")
    return redirect(url_for("index"))

@app.route("/add-schedule", methods=["POST"])
def add_schedule():
    source = request.form.get("schedule_source"); interval = request.form.get("schedule_interval"); time_str = request.form.get("schedule_time")
    if not source or not os.path.exists(source):
        flash(f"Hata: Zamanlama için kaynak dizin '{source}' bulunamadı!", "danger"); return redirect(url_for("index"))
    hour, minute = map(int, time_str.split(':'))
    job_id = f"backup_{re.sub(r'[^a-zA-Z0-9]', '_', source.strip('/'))}"
    trigger_args = {'hour': hour, 'minute': minute}
    if interval == 'weekly': trigger_args['day_of_week'] = 'sun'
    elif interval == 'monthly': trigger_args['day'] = 1
    try:
        scheduler.add_job(perform_backup_job, 'cron', args=[source, BACKUP_ROOT_DIR], id=job_id, name=f"Otomatik Yedek: {source}", replace_existing=True, **trigger_args)
        flash(f"'{source}' için otomatik yedekleme planı oluşturuldu/güncellendi.", "success")
    except Exception as e: flash(f"Plan oluşturulurken hata: {e}", "danger")
    return redirect(url_for("index"))

@app.route("/delete-schedule/<job_id>")
def delete_schedule(job_id):
    try: scheduler.remove_job(job_id); flash(f"'{job_id}' numaralı yedekleme planı silindi.", "success")
    except Exception as e: flash(f"Plan silinirken hata: {e}", "danger")
    return redirect(url_for("index"))

@app.route("/backup-disk", methods=["POST"])
def backup_disk(): 
    source_disk = request.form.get("source_disk")
    if not source_disk:
        flash("Hata: Kaynak disk seçilmedi!", "danger"); return redirect(url_for("index"))
    try:
        safe_disk_name = os.path.basename(source_disk).replace('/', '_'); backup_id = f"disk_image_{safe_disk_name}"
        dest_path = os.path.join(BACKUP_ROOT_DIR, backup_id); os.makedirs(dest_path, exist_ok=True)
        date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M"); filename = f"{safe_disk_name}_{date}.img.gz"
        full_path = os.path.join(dest_path, filename); cmd = f"dd if={source_disk} bs=4M status=progress | gzip > {full_path}"
        log_message(f"Disk imajı komutu başlatılıyor: {cmd}")
        process = subprocess.run(cmd, shell=True, check=True, stderr=subprocess.PIPE, text=True)
        log_message(f"DD komutu çıktısı:\n{process.stderr}"); log_message(f"Disk imajı tamamlandı: {full_path}")
        flash(f"Disk imajı '{source_disk}' başarıyla alındı: {filename}", "success")
    except Exception as e:
        log_message(f"DISK İMAJI HATASI: {e}"); flash(f"Disk imajı alınırken hata oluştu: {e}. İzinleri (sudo) kontrol edin.", "danger")
    return redirect(url_for("index"))

@app.route("/sync-files", methods=["POST"])
def sync_files(): 
    source = request.form.get("sync_source"); destination = request.form.get("sync_dest")
    if not source or not os.path.exists(source):
        flash(f"Hata: Kaynak dizin '{source}' bulunamadı!", "danger"); return redirect(url_for("index"))
    if not destination:
        flash("Hata: Hedef dizin belirtilmedi!", "danger"); return redirect(url_for("index"))
    os.makedirs(destination, exist_ok=True)
    try:
        cmd = f"rsync -avh --delete '{source}/' '{destination}'"; log_message(f"Senkronizasyon komutu başlatılıyor: {cmd}")
        subprocess.run(cmd, shell=True, check=True)
        log_message(f"Senkronizasyon tamamlandı: {source} -> {destination}")
        flash(f"'{source}' dizini '{destination}' ile başarıyla senkronize edildi.", "success")
    except Exception as e:
        log_message(f"SENKRONİZASYON HATASI: {e}"); flash(f"Senkronizasyon sırasında hata: {e}", "danger")
    return redirect(url_for("index"))

@app.route('/download/<backup_id>/<filename>')
def download_file(backup_id, filename):
    if '..' in backup_id or '/' in backup_id or '..' in filename or '/' in filename: return "Geçersiz dosya yolu", 400
    try:
        directory = os.path.join(os.path.abspath(BACKUP_ROOT_DIR), backup_id)
        return send_from_directory(directory, filename, as_attachment=True)
    except FileNotFoundError:
        flash(f"İndirilecek dosya bulunamadı: {filename}", "danger"); return redirect(url_for('index'))
    except Exception as e:
        flash(f"Dosya indirilirken bir hata oluştu: {e}", "danger"); return redirect(url_for('index'))

@app.route('/delete/<backup_id>/<filename>')
def delete_file(backup_id, filename):
    if '..' in backup_id or '/' in backup_id or '..' in filename or '/' in filename: return "Geçersiz dosya yolu", 400
    try:
        file_path = os.path.join(BACKUP_ROOT_DIR, backup_id, filename)
        if not os.path.abspath(file_path).startswith(os.path.abspath(BACKUP_ROOT_DIR)): return "Yetkisiz Erişim", 403
        os.remove(file_path); flash(f"'{filename}' dosyası başarıyla silindi.", "success"); log_message(f"Yedek silindi: {file_path}")
    except FileNotFoundError: flash(f"Silinecek dosya bulunamadı: {filename}", "warning")
    except Exception as e: flash(f"Dosya silinirken hata: {e}", "danger"); log_message(f"SİLME HATASI: {e}")
    return redirect(url_for("index"))

# --- FTP ROTALARI ---
@app.route("/ftp")
def ftp_page():
    return render_template("ftp.html")

@app.route("/ftp-connect", methods=["POST"])
def ftp_connect():
    data = request.json
    session['ftp_details'] = { 'host': data['host'], 'port': int(data['port']), 'user': data['user'], 'pass': data['pass'] }
    ftp, error = _get_ftp_connection_from_session()
    if error:
        session.pop('ftp_details', None); return jsonify({'status': 'error', 'message': error})
    welcome_message = ftp.getwelcome(); ftp.quit()
    return jsonify({'status': 'success', 'message': welcome_message})

@app.route("/ftp-list", methods=["POST"])
def ftp_list():
    ftp, error = _get_ftp_connection_from_session()
    if error: return jsonify({'status': 'error', 'message': error})
    data = request.json
    remote_path = data.get('remote_path', '.'); local_path = data.get('local_path', BACKUP_ROOT_DIR)
    safe_local_path = os.path.abspath(os.path.join(BACKUP_ROOT_DIR, local_path.replace(BACKUP_ROOT_DIR, '', 1)))
    if not safe_local_path.startswith(os.path.abspath(BACKUP_ROOT_DIR)): safe_local_path = BACKUP_ROOT_DIR
    try:
        ftp.cwd(remote_path)
        remote_files = [{'name': item[0], 'type': item[1].get('type')} for item in ftp.mlsd()]
        local_files = [{'name': item, 'type': 'dir' if os.path.isdir(os.path.join(safe_local_path, item)) else 'file'} for item in os.listdir(safe_local_path)]
        response = { 'status': 'success', 'remote_files': remote_files, 'local_files': local_files, 'remote_path': ftp.pwd(), 'local_path': safe_local_path }
        ftp.quit(); return jsonify(response)
    except ftplib.all_errors as e:
        ftp.quit(); return jsonify({'status': 'error', 'message': str(e)})

@app.route('/ftp-upload', methods=['POST'])
def ftp_upload():
    ftp, error = _get_ftp_connection_from_session();
    if error: return jsonify({'status': 'error', 'message': error})
    data = request.json
    local_file_path = os.path.join(data['local_path'], data['filename']); remote_file_path = os.path.join(data['remote_path'], data['filename'])
    if not os.path.abspath(local_file_path).startswith(os.path.abspath(BACKUP_ROOT_DIR)): return jsonify({'status': 'error', 'message': 'Yetkisiz dosya erişimi.'})
    try:
        with open(local_file_path, 'rb') as f: ftp.storbinary(f'STOR {remote_file_path}', f)
        ftp.quit(); return jsonify({'status': 'success', 'message': f'{data["filename"]} başarıyla yüklendi.'})
    except ftplib.all_errors as e:
        ftp.quit(); return jsonify({'status': 'error', 'message': str(e)})

@app.route('/ftp-download', methods=['POST'])
def ftp_download():
    ftp, error = _get_ftp_connection_from_session();
    if error: return jsonify({'status': 'error', 'message': error})
    data = request.json
    remote_file_path = os.path.join(data['remote_path'], data['filename']); local_file_path = os.path.join(data['local_path'], data['filename'])
    if not os.path.abspath(data['local_path']).startswith(os.path.abspath(BACKUP_ROOT_DIR)): return jsonify({'status': 'error', 'message': 'Güvenli olmayan bir konuma indirme yapılamaz.'})
    try:
        with open(local_file_path, 'wb') as f: ftp.retrbinary(f'RETR {remote_file_path}', f.write)
        ftp.quit(); return jsonify({'status': 'success', 'message': f'{data["filename"]} başarıyla indirildi.'})
    except ftplib.all_errors as e:
        ftp.quit(); return jsonify({'status': 'error', 'message': str(e)})

@app.route('/ftp-create-directory', methods=['POST'])
def ftp_create_directory():
    ftp, error = _get_ftp_connection_from_session()
    if error: return jsonify({'status': 'error', 'message': error})
    data = request.json
    remote_path = data.get('remote_path', '.'); new_dir_name = data.get('dir_name')
    if not new_dir_name: return jsonify({'status': 'error', 'message': 'Klasör adı belirtilmedi.'})
    try:
        new_path = os.path.join(remote_path, new_dir_name)
        ftp.mkd(new_path); ftp.quit()
        return jsonify({'status': 'success', 'message': f"'{new_dir_name}' klasörü oluşturuldu."})
    except ftplib.all_errors as e:
        ftp.quit(); return jsonify({'status': 'error', 'message': str(e)})

@app.route('/ftp-upload-folder', methods=['POST'])
def ftp_upload_folder():
    ftp, error = _get_ftp_connection_from_session();
    if error: return jsonify({'status': 'error', 'message': error})
    data = request.json
    local_folder_path = os.path.join(data['local_path'], data['foldername'])
    remote_folder_path = os.path.join(data['remote_path'], data['foldername']).replace("\\", "/")
    if not os.path.abspath(local_folder_path).startswith(os.path.abspath(BACKUP_ROOT_DIR)): return jsonify({'status': 'error', 'message': 'Yetkisiz dosya erişimi.'})
    try:
        try: ftp.mkd(remote_folder_path)
        except ftplib.all_errors: pass # Klasör zaten var olabilir
        ftp_upload_folder_recursive(ftp, local_folder_path, remote_folder_path); ftp.quit()
        return jsonify({'status': 'success', 'message': f"'{data['foldername']}' klasörü başarıyla yüklendi."})
    except (ftplib.all_errors, OSError) as e:
        ftp.quit(); return jsonify({'status': 'error', 'message': str(e)})

@app.route('/ftp-download-folder', methods=['POST'])
def ftp_download_folder():
    ftp, error = _get_ftp_connection_from_session();
    if error: return jsonify({'status': 'error', 'message': error})
    data = request.json
    remote_folder_path = os.path.join(data['remote_path'], data['foldername']).replace("\\", "/")
    local_folder_path = os.path.join(data['local_path'], data['foldername'])
    if not os.path.abspath(data['local_path']).startswith(os.path.abspath(BACKUP_ROOT_DIR)): return jsonify({'status': 'error', 'message': 'Güvenli olmayan bir konuma indirme yapılamaz.'})
    try:
        ftp_download_folder_recursive(ftp, remote_folder_path, local_folder_path); ftp.quit()
        return jsonify({'status': 'success', 'message': f"'{data['foldername']}' klasörü başarıyla indirildi."})
    except (ftplib.all_errors, OSError) as e:
        ftp.quit(); return jsonify({'status': 'error', 'message': str(e)})

@app.route("/ftp-disconnect", methods=["POST"])
def ftp_disconnect():
    session.pop('ftp_details', None); return jsonify({'status': 'success', 'message': 'Bağlantı kesildi.'})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
