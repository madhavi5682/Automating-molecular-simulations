# MolSim Pipeline — Complete Deployment Guide
## From zero to live in ~1 hour

---

## Files in this package

```
molsim-pipeline.html   ← Web UI (hosted on GitHub Pages)
server.py              ← Simulation backend (runs on Hugging Face)
Dockerfile             ← Installs LAMMPS + Packmol + Moltemplate
requirements.txt       ← Python dependencies
README.md              ← This file
```

---

## PART 1 — GitHub Setup (15 minutes)

### Step 1 — Create a GitHub account
1. Go to **github.com**
2. Click **Sign up**
3. Choose a username (e.g. `rahul-chem`) — this appears in your URL
4. Use the free plan

---

### Step 2 — Create a new repository
1. Click the **+** button (top right) → **New repository**
2. Repository name: `molsim-pipeline`
3. Visibility: **Public** ← required for free GitHub Pages
4. Click **Create repository**

---

### Step 3 — Upload all 5 files
1. In your new empty repo, click **Add file** → **Upload files**
2. Drag and drop all 5 files from this package:
   - `molsim-pipeline.html`
   - `server.py`
   - `Dockerfile`
   - `requirements.txt`
   - `README.md`
3. Scroll down → click **Commit changes**

Your repo should now look like:
```
github.com/YOUR_USERNAME/molsim-pipeline/
├── molsim-pipeline.html
├── server.py
├── Dockerfile
├── requirements.txt
└── README.md
```

---

### Step 4 — Enable GitHub Pages
1. Go to your repo → click **Settings** tab
2. Left sidebar → click **Pages**
3. Under "Source" → select **Deploy from a branch**
4. Branch: **main** | Folder: **/ (root)**
5. Click **Save**
6. Wait 2 minutes, then your web UI is live at:
```
https://YOUR_USERNAME.github.io/molsim-pipeline/molsim-pipeline.html
```
**Anyone on earth can open this URL — no login needed.**

---

## PART 2 — Hugging Face Setup (20 minutes)

### Step 5 — Create a Hugging Face account
1. Go to **huggingface.co**
2. Click **Sign Up**
3. Choose a username (same as GitHub is fine)
4. Free plan

---

### Step 6 — Create a new Space
1. Click your profile picture (top right) → **New Space**
2. Fill in:
   - **Space name**: `molsim-backend`
   - **License**: MIT
   - **SDK**: **Docker** ← important, select this one
   - **Visibility**: Public
3. Click **Create Space**

You'll see an empty space with a file editor.

---

### Step 7 — Connect to your GitHub repo
1. In your Space, click **Files** tab
2. Click **Add file** → **Upload files**
3. Upload these 3 files from your package:
   - `Dockerfile`
   - `server.py`
   - `requirements.txt`
4. Click **Commit changes to main**

Hugging Face will now **automatically**:
- Read your Dockerfile
- Spin up a Ubuntu Linux machine
- Install LAMMPS, Packmol, Moltemplate
- Start your FastAPI server

This takes **5-10 minutes**. You'll see a build log. Wait for it to say **Running**.

Your backend is now live at:
```
https://YOUR_HF_USERNAME-molsim-backend.hf.space
```

---

### Step 8 — Test the backend
Open this URL in your browser:
```
https://YOUR_HF_USERNAME-molsim-backend.hf.space/api/health
```

You should see something like:
```json
{
  "api": "ok",
  "moltemplate": true,
  "packmol": true,
  "lammps": true
}
```
If all 3 are `true`, everything is installed correctly.

---

## PART 3 — Connect the two (5 minutes)

### Step 9 — Update the API URL in the HTML file
1. Open `molsim-pipeline.html` in any text editor (Notepad is fine)
2. Find this line near the bottom (around line 350):
```javascript
const API_BASE = "https://YOUR_HF_USERNAME-YOUR_SPACE_NAME.hf.space";
```
3. Replace it with your actual Hugging Face URL:
```javascript
const API_BASE = "https://rahul-chem-molsim-backend.hf.space";
```
(use your actual username and space name)

4. Save the file

---

### Step 10 — Re-upload the updated HTML to GitHub
1. Go to your GitHub repo
2. Click on `molsim-pipeline.html`
3. Click the **pencil icon** (Edit this file)
4. Select all → paste your updated file content
5. Click **Commit changes**

GitHub Pages updates automatically in ~1 minute.

---

## PART 4 — Test it works (5 minutes)

### Step 11 — Open the web app
Go to:
```
https://YOUR_USERNAME.github.io/molsim-pipeline/molsim-pipeline.html
```

You should see:
- **⬤ Connected** (green) in the top right

If it says **Offline**, the Hugging Face space might be sleeping.
Wait 30 seconds and refresh — it wakes up automatically.

---

### Step 12 — Run a test simulation
1. Upload a .pdb and .lt file from LigParGen
2. Add a molecule (name + count)
3. Leave parameters as default
4. Click **Launch Simulation**
5. Watch the live log
6. Download results

---

## How to update your code later

Whenever you change `server.py` or `molsim-pipeline.html`:

**For the HTML (web UI):**
1. Go to GitHub repo → click the file → edit → commit
2. GitHub Pages updates in ~1 minute

**For the backend:**
1. Go to Hugging Face Space → Files tab → click the file → edit → commit
2. Hugging Face rebuilds the container in ~5-10 minutes
3. Your backend is updated with zero downtime

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "Offline" badge | Space is sleeping. Wait 30 sec, refresh. |
| "Tools missing" in health check | Dockerfile failed to install tools. Check build logs in HF Space. |
| Upload fails | Check browser console (F12) for CORS errors. Make sure API_BASE URL is correct. |
| Simulation errors | Click download on `pipeline.log` for detailed error messages. |
| HF build fails | Check the build log in your Space — it shows exactly which install step failed. |

---

## What each person needs to use this

- A modern browser (Chrome, Firefox, Edge)
- Internet connection
- That's it. Nothing else.

---

## Architecture summary

```
Student's Browser           GitHub Pages              Hugging Face
(any PC, no installs)      (hosts HTML, free)        (runs simulation, free)

Opens web app         ←    molsim-pipeline.html
Uploads .pdb + .lt    ──────────────────────────────► server.py
                                                       ├── moltemplate.sh
                                                       ├── packmol
                                                       └── lmp (LAMMPS)
Downloads results.zip ◄──────────────────────────────
```

**Total cost: $0**
**Works from: any PC on earth with a browser**
