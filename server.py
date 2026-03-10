"""
MolSim Pipeline — FastAPI Backend
Configured for Hugging Face Spaces (port 7860)

This file runs inside the Docker container on Hugging Face.
It receives files from the web UI, runs Moltemplate → Packmol → LAMMPS,
and serves the results back for download.
"""

import os
import uuid
import shutil
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ─────────────────────────────────────────────────────────────
# App setup
# ─────────────────────────────────────────────────────────────

app = FastAPI(title="MolSim Pipeline API", version="1.0.0")

# Allow requests from GitHub Pages (and anywhere else)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────
# Paths & tool names (pre-installed in Docker container)
# ─────────────────────────────────────────────────────────────

WORK_DIR        = Path("/tmp/molsim")
MOLTEMPLATE_BIN = "moltemplate.sh"
PACKMOL_BIN     = "packmol"
LAMMPS_BIN      = "lmp"          # Ubuntu package installs as 'lmp'

WORK_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# In-memory job store
# ─────────────────────────────────────────────────────────────

jobs: dict[str, dict] = {}

# ─────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────

class MoleculeConfig(BaseModel):
    name: str
    count: int
    pdb_filename: str
    lt_filename: str

class BoxConfig(BaseModel):
    x: float = 40.0
    y: float = 40.0
    z: float = 40.0
    tolerance: float = 2.0

class LammpsConfig(BaseModel):
    ensemble: str  = "NVT"
    temperature: float = 300.0
    pressure: float    = 1.0
    timestep: float    = 1.0
    run_steps: int     = 500000
    thermo_freq: int   = 1000
    dump_freq: int     = 1000
    cutoff: float      = 12.0
    minimize: bool     = True

class RunConfig(BaseModel):
    molecules: list[MoleculeConfig]
    box: BoxConfig       = BoxConfig()
    lammps: LammpsConfig = LammpsConfig()

# ─────────────────────────────────────────────────────────────
# Logging helpers
# ─────────────────────────────────────────────────────────────

def log(job_id: str, message: str, level: str = "info"):
    entry = {"t": datetime.now().strftime("%H:%M:%S"), "msg": message, "level": level}
    jobs[job_id]["log"].append(entry)
    log_file = WORK_DIR / job_id / "pipeline.log"
    with open(log_file, "a") as f:
        f.write(f"[{entry['t']}] [{level.upper()}] {message}\n")

def set_stage(job_id: str, stage: str, progress: int):
    jobs[job_id]["stage"]    = stage
    jobs[job_id]["progress"] = progress

def run_cmd(job_id: str, cmd: str, cwd: Path, timeout: int = 3600) -> bool:
    log(job_id, f"$ {cmd}", level="cmd")
    try:
        proc = subprocess.Popen(
            cmd, shell=True, cwd=str(cwd),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True
        )
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                log(job_id, line)
        proc.wait(timeout=timeout)
        if proc.returncode != 0:
            log(job_id, f"Command failed with exit code {proc.returncode}", level="error")
            return False
        return True
    except Exception as e:
        log(job_id, f"Command error: {e}", level="error")
        return False

# ─────────────────────────────────────────────────────────────
# File writers
# ─────────────────────────────────────────────────────────────

def write_system_lt(job_dir: Path, config: RunConfig):
    lines = []
    for mol in config.molecules:
        lines.append(f'import "{mol.lt_filename}"')
    lines.append("")
    for mol in config.molecules:
        lines.append(f'{mol.name.lower()} = new {mol.name}[{mol.count}]')
    lines.append("")
    b = config.box
    lines.append('write_once("Data Boundary") {')
    lines.append(f"  0.0  {b.x}  xlo xhi")
    lines.append(f"  0.0  {b.y}  ylo yhi")
    lines.append(f"  0.0  {b.z}  zlo zhi")
    lines.append("}")
    (job_dir / "system.lt").write_text("\n".join(lines))

def write_packmol_inp(job_dir: Path, config: RunConfig):
    b = config.box
    margin = 2.0
    lines = [
        f"tolerance {config.box.tolerance}",
        "filetype pdb",
        "output packed.pdb",
        "",
    ]
    for mol in config.molecules:
        lines += [
            f"structure {mol.pdb_filename}",
            f"  number {mol.count}",
            f"  inside box {margin} {margin} {margin} "
            f"{b.x-margin} {b.y-margin} {b.z-margin}",
            "end structure",
            "",
        ]
    (job_dir / "pack.inp").write_text("\n".join(lines))

def write_lammps_input(job_dir: Path, config: RunConfig):
    lmp = config.lammps
    minimize_block = ""
    if lmp.minimize:
        minimize_block = """
# Energy minimization
minimize        1.0e-4 1.0e-6 1000 10000
reset_timestep  0
"""
    if lmp.ensemble == "NVT":
        thermostat = (f"fix  1 all nvt temp {lmp.temperature} "
                      f"{lmp.temperature} $(100.0*dt)")
    elif lmp.ensemble == "NPT":
        thermostat = (f"fix  1 all npt temp {lmp.temperature} "
                      f"{lmp.temperature} $(100.0*dt) "
                      f"iso {lmp.pressure} {lmp.pressure} $(1000.0*dt)")
    else:
        thermostat = "fix  1 all nve"

    script = f"""# MolSim Pipeline — Auto-generated LAMMPS input
# {datetime.now().isoformat()}

include         system.in.init
read_data       system.data
include         system.in.settings

neighbor        2.0 bin
neigh_modify    every 1 delay 0 check yes
pair_modify     tail yes

thermo          {lmp.thermo_freq}
thermo_style    custom step temp press pe ke etotal density
{minimize_block}
timestep        {lmp.timestep}
{thermostat}

dump            1 all atom {lmp.dump_freq} traj.lammpstrj
dump_modify     1 sort id

run             {lmp.run_steps}
write_data      final.data
"""
    (job_dir / "system.in").write_text(script)

# ─────────────────────────────────────────────────────────────
# Pipeline runner (background thread)
# ─────────────────────────────────────────────────────────────

def run_pipeline(job_id: str, config: RunConfig):
    job_dir = WORK_DIR / job_id
    try:
        # Stage 1: Moltemplate
        set_stage(job_id, "moltemplate", 10)
        log(job_id, "══ STAGE 1: Moltemplate ══", "step")
        write_system_lt(job_dir, config)
        ok = run_cmd(job_id, f"{MOLTEMPLATE_BIN} system.lt", job_dir)
        if not ok:
            raise RuntimeError("Moltemplate failed")
        log(job_id, "✓ Moltemplate complete", "success")
        set_stage(job_id, "moltemplate", 30)

        # Stage 2: Packmol
        set_stage(job_id, "packmol", 35)
        log(job_id, "══ STAGE 2: Packmol ══", "step")
        write_packmol_inp(job_dir, config)
        ok = run_cmd(job_id, f"{PACKMOL_BIN} < pack.inp", job_dir)
        if not ok:
            raise RuntimeError("Packmol failed")
        log(job_id, "✓ Packmol complete", "success")
        set_stage(job_id, "packmol", 55)

        # Stage 3: LAMMPS
        set_stage(job_id, "lammps", 60)
        log(job_id, "══ STAGE 3: LAMMPS ══", "step")
        write_lammps_input(job_dir, config)
        ok = run_cmd(job_id, f"{LAMMPS_BIN} -in system.in", job_dir, timeout=7200)
        if not ok:
            raise RuntimeError("LAMMPS failed")
        log(job_id, "✓ LAMMPS complete", "success")
        set_stage(job_id, "lammps", 88)

        # Stage 4: Package results
        set_stage(job_id, "post", 90)
        log(job_id, "══ STAGE 4: Packaging ══", "step")
        output_files = [
            "system.data", "system.in", "system.in.init",
            "system.in.settings", "traj.lammpstrj", "log.lammps",
            "packed.pdb", "pipeline.log",
        ]
        with zipfile.ZipFile(job_dir / "results.zip", "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in output_files:
                fpath = job_dir / fname
                if fpath.exists():
                    zf.write(fpath, fname)
                    log(job_id, f"  packed: {fname}")

        log(job_id, "✓ results.zip ready", "success")
        log(job_id, "══ Pipeline complete! ══", "step")
        jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "finished_at": datetime.now().isoformat(),
        })

    except Exception as e:
        log(job_id, f"PIPELINE ERROR: {e}", "error")
        jobs[job_id].update({"status": "error", "error": str(e)})

# ─────────────────────────────────────────────────────────────
# API Routes
# ─────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"message": "MolSim Pipeline API", "status": "running", "version": "1.0.0"}

@app.get("/api/health")
def health():
    return {
        "api": "ok",
        "moltemplate": shutil.which(MOLTEMPLATE_BIN) is not None,
        "packmol":     shutil.which(PACKMOL_BIN) is not None,
        "lammps":      shutil.which(LAMMPS_BIN) is not None,
    }

@app.post("/api/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    job_id  = str(uuid.uuid4())[:8].upper()
    job_dir = WORK_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for upload in files:
        dest = job_dir / upload.filename
        dest.write_bytes(await upload.read())
        saved.append(upload.filename)
    jobs[job_id] = {
        "job_id": job_id, "status": "uploaded",
        "stage": "idle", "progress": 0,
        "log": [], "files": saved,
        "created_at": datetime.now().isoformat(),
        "finished_at": None, "error": None,
    }
    return {"job_id": job_id, "files_saved": saved}

@app.post("/api/run/{job_id}")
def run_simulation(job_id: str, config: RunConfig, background: BackgroundTasks):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found. Upload files first.")
    if jobs[job_id]["status"] == "running":
        raise HTTPException(409, "Job already running.")
    jobs[job_id].update({"status": "running", "progress": 5})
    background.add_task(run_pipeline, job_id, config)
    return {"job_id": job_id, "status": "started"}

@app.get("/api/status/{job_id}")
def get_status(job_id: str, since_log: int = 0):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    job = jobs[job_id]
    return {
        "job_id":      job_id,
        "status":      job["status"],
        "stage":       job["stage"],
        "progress":    job["progress"],
        "log":         job["log"][since_log:],
        "log_total":   len(job["log"]),
        "error":       job.get("error"),
        "finished_at": job.get("finished_at"),
    }

@app.get("/api/download/{job_id}/{filename}")
def download_file(job_id: str, filename: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    safe_name = Path(filename).name
    file_path = WORK_DIR / job_id / safe_name
    if not file_path.exists():
        raise HTTPException(404, f"File '{safe_name}' not found")
    return FileResponse(str(file_path), filename=safe_name,
                        media_type="application/octet-stream")

@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    job_dir = WORK_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    del jobs[job_id]
    return {"deleted": job_id}
