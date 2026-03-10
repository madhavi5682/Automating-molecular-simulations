# ─────────────────────────────────────────────────────────────────
# MolSim Pipeline — Dockerfile
# Hugging Face Spaces expects port 7860
# ─────────────────────────────────────────────────────────────────

FROM ubuntu:22.04

# Prevent interactive prompts during install
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# ── System packages ───────────────────────────────────────────────
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    wget \
    curl \
    git \
    build-essential \
    gfortran \
    lammps \
    packmol \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Moltemplate (Python-based, install via pip) ───────────────────
RUN pip3 install moltemplate

# ── Python server dependencies ────────────────────────────────────
COPY requirements.txt .
RUN pip3 install -r requirements.txt

# ── Copy application code ─────────────────────────────────────────
COPY server.py .

# ── Create work directory for simulation jobs ─────────────────────
RUN mkdir -p /tmp/molsim

# ── Hugging Face Spaces requires port 7860 ────────────────────────
EXPOSE 7860

# ── Start the server ──────────────────────────────────────────────
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]
