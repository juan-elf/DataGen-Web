# Deploy DataGen Web — Panduan Langkah demi Langkah

> Urutan: **GitHub → Render (backend) → Vercel (frontend) → keep-alive → tes → domain asli.**
> Semua layanan di tahap 0–5 gratis. Domain (tahap 6) satu-satunya yang berbayar.
>
> Estimasi waktu: ±45–60 menit untuk tahap 0–5.

---

## Tahap 0 — Push ke GitHub

Vercel dan Render deploy dari repo GitHub, jadi ini prasyarat.

```powershell
cd e:\DataGen
git init
git add .
git commit -m "Initial commit: DataGen web (FastAPI backend + Next.js frontend)"
```

Buat repo di GitHub (mis. `datagen-web`, boleh private), lalu:

```powershell
git remote add origin https://github.com/<username>/datagen-web.git
git branch -M main
git push -u origin main
```

**✅ Cek sebelum push:** `git status` TIDAK boleh menampilkan `backend/.env` atau
`frontend/.env.local` — keduanya sudah di-gitignore, tapi pastikan. Jangan pernah
commit file berisi API key/password.

---

## Tahap 1 — Deploy Backend ke Render

1. Daftar/login di [render.com](https://render.com) (bisa pakai akun GitHub).
2. **New → Web Service** → connect repo `datagen-web`.
3. Isi konfigurasi:
   - **Root Directory:** `backend`
   - **Runtime/Language:** Docker (otomatis terdeteksi dari `backend/Dockerfile`)
   - **Region:** Singapore (terdekat dari Supabase ap-southeast-2 & Indonesia)
   - **Instance Type:** Free
4. **Environment Variables** — salin dari `backend/.env` lokal, dengan perbedaan berikut:

   | Variabel | Nilai |
   |---|---|
   | `OPENROUTER_API_KEY` | (sama dengan lokal) |
   | `AGENT_MODEL` | (sama dengan lokal) |
   | `GUARDRAIL_MODEL` | (sama dengan lokal) |
   | `TAVILY_API_KEY` | (sama dengan lokal) |
   | `DATABASE_URL` | (sama dengan lokal — pooler `aws-1-ap-southeast-2`) |
   | `WRITE_DATABASE_URL` | (sama dengan lokal) |
   | `WORKSPACE_TTL_DAYS` | `7` |
   | `SECRET_KEY` | **generate baru** — lihat perintah di bawah ⬇ |
   | `COOKIE_SECURE` | **`true`** (produksi pakai HTTPS — beda dari lokal!) |
   | `FRONTEND_ORIGIN` | kosongkan dulu / isi placeholder — diisi di Tahap 3 |
   | `CLEANUP_TOKEN` | **generate baru** — lihat perintah di bawah ⬇ |

   Generate `SECRET_KEY` dan `CLEANUP_TOKEN` (jalankan 2× untuk dua nilai berbeda):

   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

5. (Opsional tapi bagus) **Health Check Path:** `/health`
6. **Create Web Service** → tunggu build (~5 menit).
7. Catat URL-nya, mis. `https://datagen-backend.onrender.com`.
8. **Tes:** buka `https://<backend-url>/health/db` → harus `{"status":"ok","db":"reachable"}`.

https://datagen-web.onrender.com/
---

## Tahap 2 — Deploy Frontend ke Vercel

1. Login [vercel.com](https://vercel.com) (pakai akun GitHub).
2. **Add New → Project** → import repo `datagen-web`.
3. Konfigurasi:
   - **Root Directory:** `frontend` ⚠️ (wajib — ini monorepo)
   - **Framework Preset:** Next.js (otomatis)
4. **Environment Variables:**

   | Variabel | Nilai |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | `https://datagen-backend.onrender.com` (URL dari Tahap 1, **tanpa** trailing slash) |

5. **Deploy** → tunggu (~2 menit) → catat URL, mis. `https://datagen-web.vercel.app`.
https://data-gen-web.vercel.app/
---

## Tahap 3 — Hubungkan CORS Backend ke Frontend

1. Kembali ke Render → service backend → **Environment**.
2. Isi `FRONTEND_ORIGIN` = `https://datagen-web.vercel.app` (URL Vercel dari Tahap 2,
   tanpa trailing slash).
3. Save → Render otomatis restart.

---

## Tahap 4 — Aktifkan Keep-Alive (wajib untuk Render free)

Render free tidur setelah 15 menit idle (cold start ~30–60 detik), dan Supabase free
pause setelah 1 minggu idle. Workflow `.github/workflows/keepalive.yml` sudah ada di
repo — tinggal isi secrets:

1. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:
   - `BACKEND_URL` = `https://datagen-backend.onrender.com` (tanpa trailing slash)
   - `CLEANUP_TOKEN` = nilai yang sama dengan env `CLEANUP_TOKEN` di Render
2. Tab **Actions** → pastikan workflow "Keep-alive + workspace TTL sweep" aktif
   (kalau repo baru, klik "Enable workflows").
3. Tes manual: buka workflow → **Run workflow** → kedua step harus hijau.

---

## Tahap 5 — Tes End-to-End

Dari browser (Chrome dulu — lihat catatan Safari di Tahap 6):

- [ ] `https://<frontend>.vercel.app` → landing page tampil
- [ ] Get Started → upload CSV kecil → sukses, profil tabel muncul
- [ ] Chat → tanya sesuatu tentang datanya → jawaban + blok SQL muncul
- [ ] Insight Report → generate → progress jalan → laporan tampil
- [ ] Refresh halaman → chat/upload masih di workspace yang sama (cookie bertahan)

**Jika upload/chat gagal dengan error CORS** (cek Console browser): pastikan
`FRONTEND_ORIGIN` di Render persis sama dengan origin Vercel — `https://`, tanpa
trailing slash, tanpa path.

**Jika request pertama lambat ~60 detik:** itu cold start Render free. Setelah
keep-alive aktif (Tahap 4), ini hampir tidak akan terjadi lagi.

---

## Tahap 6 — Domain Asli (setelah semua di atas jalan)

> **Kenapa perlu:** frontend di `*.vercel.app` + backend di `*.onrender.com` = beda
> site → **Safari memblokir cookie workspace** (third-party). Dengan satu domain dan
> subdomain untuk API, keduanya jadi *same-site* → cookie jalan di semua browser.

### 6a. Beli domain

| Opsi | Harga/tahun | Catatan |
|---|---|---|
| `.my.id` | ~Rp10–20rb | Termurah (registrar lokal: Domainesia, Niagahoster, dll.) |
| `.com` | ~Rp160rb | Paling kredibel untuk portfolio — beli via Cloudflare/Porkbun (at-cost) |

Misal beli: `datagen.my.id`.

### 6b. Pasang di Vercel (frontend)

1. Vercel project → **Settings → Domains** → add `datagen.my.id`.
2. Ikuti instruksi DNS (A record / CNAME) di dashboard registrar/Cloudflare.

### 6c. Pasang di Render (backend)

1. Render service → **Settings → Custom Domains** → add `api.datagen.my.id`.
2. Tambahkan CNAME `api` → `<backend>.onrender.com` di DNS.

### 6d. Update konfigurasi (3 nilai)

| Di mana | Variabel | Nilai baru |
|---|---|---|
| Vercel env | `NEXT_PUBLIC_API_URL` | `https://api.datagen.my.id` |
| Render env | `FRONTEND_ORIGIN` | `https://datagen.my.id` |
| GitHub secret | `BACKEND_URL` | `https://api.datagen.my.id` |

Redeploy frontend (Vercel → Deployments → Redeploy) supaya `NEXT_PUBLIC_API_URL`
baru ter-bundle. Render cukup restart otomatis saat env disave.

- [ ] Tes ulang checklist Tahap 5 — kali ini termasuk di Safari/iPhone.

---

## Catatan Keamanan Produksi (sudah disiapkan, jangan dilewati)

- `SECRET_KEY` produksi **harus berbeda** dari lokal dan tidak boleh kosong —
  kalau kosong, workspace semua user reset setiap backend restart.
- `COOKIE_SECURE=true` di produksi (HTTPS). Nilai `false` hanya untuk lokal.
- `DATABASE_URL` saat ini memakai role `postgres` (full access). Untuk hardening
  nanti: buat role read-only untuk `DATABASE_URL` dan pisahkan dari
  `WRITE_DATABASE_URL` — langkahnya ada di README.md bagian "Supabase setup".
- Supabase free tier: 500MB — TTL sweep 7 hari sudah aktif via keep-alive cron,
  jadi workspace terbengkalai terhapus otomatis.
