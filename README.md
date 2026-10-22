# WebSocket Signaling Service

Backend layanan sinyalisasi panggilan (Softphone / WebRTC / SIP Signaling) berbasis **FastAPI** dan **python-socketio (ASGI)** dengan integrasi **Asterisk PJSIP** dan pencatatan riwayat panggilan (*Call Logs*) presisi ke database MySQL.

---

## 🚀 Fitur Utama

- **Autentikasi Token & Kebijakan 1 Extension 1 Socket:**
  - Login via HTTP REST API (`/auth/login`) untuk memperoleh token otentikasi.
  - Sesi socket tervalidasi ke database (`users_account`).
  - Kebijakan single-device: login baru pada extension yang sama otomatis menendang perangkat lama via event `session:replaced`.
- **Manajemen Siklus Panggilan Presisi (`CallManager`):**
  - Alur lengkap: `invited` $\rightarrow$ `ringing` $\rightarrow$ `answered` $\rightarrow$ `ended`.
  - Timestamp selalu menggunakan jam server UTC (`datetime.utcnow()`).
  - Perhitungan durasi bicara (`billsec`) otomatis dan presisi.
  - Penutupan panggilan bersifat *idempotent* dan dilengkapi timeout ringing otomatis (60 detik).
  - Repositori database terpusat (`call_repo`) sebagai satu-satunya akses ke tabel `call_logs`.
- **Simulasi Panggilan Terjadwal (`FakePool`):**
  - Simulasi respon panggilan Asterisk tanpa perangkat fisik: mengirimkan event `call:ringing`, `call:answer`, dan `call:ended` terjadwal.
  - **Validasi nomor tujuan:** hanya angka (`to_number.isdigit()`).
  - **Batas konkurensi:** maksimal 1 panggilan aktif per extension.
  - **Otorisasi Hangup:** panggilan hanya dapat diakhiri oleh penelpon sah (*call owner*).
- **Integrasi Asterisk PJSIP & HA1 Digest Auth:**
  - Konfigurasi template modular PJSIP (`endpoint`, `auth`, `aor`) dengan `remove_existing=yes`.
  - Keamanan kredensial MD5 HA1 digest auth (`md5(username:realm:password)`).
  - Script CLI generator akun PJSIP otomatis (`scripts/generate_pjsip_account.py`).

---

## 📁 Struktur Direktori

```text
├── app/
│   ├── controller/         # FastAPI Route Controller (auth, health)
│   ├── core/               # Konfigurasi app, security, dan database async SQLAlchemy
│   ├── model/              # Model SQLAlchemy (UserAccount, CallLog)
│   ├── repository/         # Akses database users_account
│   ├── service/            # Layanan autentikasi & token
│   ├── services/           # CallManager & call_repo (logging durasi panggilan)
│   ├── sockets/            # Socket.IO AsyncServer, handlers, dan FakePool
│   ├── main.py             # Entrypoint ASGI application (FastAPI + Socket.IO)
│   └── routes.py           # Agregator router API
├── asterisk/
│   └── pjsip.conf          # Template konfigurasi PJSIP untuk server Asterisk
├── scripts/
│   └── generate_pjsip_account.py  # CLI untuk generate akun PJSIP & hash HA1
├── tests/
│   ├── test_call_flow.py   # Skenario pengujian end-to-end simulasi FakePool
│   ├── test_call_manager.py# Unit test siklus CallManager & durasi billsec
│   ├── test_call_repo.py   # Pengujian query repository tabel call_logs
│   ├── test_call_socket.py # Pengujian validasi nomor, batas panggilan, & otorisasi hangup
│   └── tester.html         # Halaman pengujian manual browser interaktif
├── Dockerfile              # Container image builder (Python 3.11-slim)
├── docker-compose.yml      # Orchestration container signaling service
├── requirements.txt        # Daftar dependency Python
├── pytest.ini              # Konfigurasi pytest asyncio
└── README.md
```

---

## ⚙️ Persyaratan Sistem

- Python 3.11+
- Database MySQL / MariaDB
- Docker & Docker Compose *(opsional, untuk deployment server)*
- Server Asterisk PBX *(untuk registrasi softphone SIP)*

---

## 🛠️ Instalasi & Menjalankan Lokal

### 1. Clone & Setup Virtual Environment
```bash
# Buat virtual environment
python3.11 -m venv venv

# Aktifkan virtual environment
source venv/bin/activate  # Linux / macOS
# venv\Scripts\activate   # Windows
```

### 2. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Konfigurasi Environment (`.env`)
Salin file `.env.example` ke `.env` lalu sesuaikan isinya:
```bash
cp .env.example .env
```
Contoh struktur variabel di `.env`:
```env
DATABASE_URL=mysql+aiomysql://<user>:<password>@<host>:3306/<database_name>
JWT_SECRET=<hasil_generate_secret_key_32_bytes_hex>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
ASTERISK_WSS_URL=wss://<domain-pbx-anda>/ws
SIP_DOMAIN=<domain-realm-sip-anda>
```

### 4. Menjalankan Server
```bash
./venv/bin/uvicorn app.main:socket_app --reload --port 8081
```
Server akan aktif di:
- **FastAPI Documentation (Swagger UI):** `http://localhost:8081/docs`
- **Socket.IO Endpoint:** `ws://localhost:8081/socket.io/`

---

## 🐳 Menjalankan dengan Docker

Untuk deployment di server menggunakan Docker:

```bash
# Build dan jalankan container di background
docker compose up -d --build

# Melihat logs container
docker compose logs -f

# Menghentikan container
docker compose down
```

---

## 🧪 Menjalankan Pengujian (Testing)

### Menjalankan Seluruh Test Suite (Pytest)
```bash
./venv/bin/pytest tests/ -v
```

### Menjalankan Pengujian Alur Interaktif (CLI)
```bash
./venv/bin/python tests/test_call_flow.py
```

### Pengujian Manual via Web Browser
Buka file tester interaktif di browser:
```bash
open tests/tester.html
```
- Gunakan akun uji database: **Extension:** `1012`, **Password:** `Pass1234`.

---

## 📞 Integrasi Asterisk PJSIP

### 1. Konfigurasi Server Asterisk
Salin template konfigurasi dari [asterisk/pjsip.conf](asterisk/pjsip.conf) ke `/etc/asterisk/pjsip.conf` pada server Asterisk Anda, lalu muat ulang konfigurasi:
```bash
asterisk -rx "pjsip reload"
asterisk -rx "pjsip show endpoints"
```

### 2. Menambah Extension Baru
Gunakan script generator untuk menghitung hash HA1 dan mencetak konfigurasi 3 section PJSIP (`endpoint`, `auth`, `aor`):
```bash
./venv/bin/python scripts/generate_pjsip_account.py --ext 1009 --password Pass1234 --save-db
```
Salin blok konfigurasi yang dihasilkan ke file `pjsip.conf` Asterisk lalu jalankan `asterisk -rx "pjsip reload"`.
