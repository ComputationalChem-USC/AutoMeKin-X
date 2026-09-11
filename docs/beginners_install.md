---
title: 1. Installation from zero
layout: home
parent: Complete tutorial for beginners
grand_parent: Tutorial
nav_order: 1
---

# Installation from zero

This page is aimed at people who **don't know the subject yet**: no
prior knowledge of computational chemistry is assumed, nor any
experience compiling software from source. Every step includes the
exact command and a short explanation of what it does and why.

{: .note }
All commands on this page were tested on Ubuntu 22.04 LTS.

## Contents

- [What is AutoMeKin?](#what-is-automekin)
- [Prerequisites](#prerequisites)
- [Installation roadmap](#roadmap)
- [Step 1 — System dependencies](#step-1)
- [Step 2 — Python with Miniconda](#step-2)
- [Step 3 — Download the source code](#step-3)
- [Step 4 — Build and install AutoMeKin](#step-4)
- [Step 5 — Set up the environment permanently](#step-5)
- [Step 6 — Verify that everything works](#step-6)
- [Step 7 — (Optional) High-level backends: ORCA, MACE and UMA](#step-7)
- [Common troubleshooting](#troubleshooting)
- [What's next](#whats-next)

## What is AutoMeKin? <a name="what-is-automekin"></a>

**AutoMeKin** (formerly called `tsscds`) is an open-source program that
automatically discovers chemical reaction mechanisms: starting from a
single input molecular structure, it locates transition states using
molecular dynamics simulations and graph theory algorithms, then
computes reaction kinetics with Monte Carlo simulations.

You don't need to understand the chemistry to install it — just basic
Linux terminal skills (copy-pasting commands, knowing which folder
you're in).

## Prerequisites <a name="prerequisites"></a>

- **Operating system:** Debian/Ubuntu-based Linux (this page uses
  Ubuntu 22.04 LTS). Build scripts also exist for CentOS/RHEL, and
  there's an alternative Singularity (container) method if you can't
  compile on your own machine.
- **Disk space:** at least 3-4 GB free for the basic installation
  (source code + Python dependencies + build artifacts). If you're also
  going to use the high-level backends from [Step 7](#step-7) (ORCA
  and/or the MACE/UMA models), set aside **15-20 GB extra** — the UMA
  model alone is about 11 GB.
- **Administrator privileges (`sudo`)** to install system packages.
- **Internet connection** to download the code and dependencies.
- **NVIDIA GPU (optional):** not required, but it greatly speeds up
  calculations with the MACE/UMA models from Step 7. Without a GPU,
  those models still work, just slower (they run on CPU).
- Know how to open a terminal and run commands. No programming
  knowledge required.

## Installation roadmap <a name="roadmap"></a>

Installing AutoMeKin from zero has several parts. It's longer than a
simple `apt install` because AutoMeKin is **compiled** from its source
code:

```
1. System packages (compilers, git, tools)
        │
        ▼
2. Python environment (Miniconda + scientific libraries)
        │
        ▼
3. Download the source code (git clone)
        │
        ▼
4. Build and install (autoreconf → configure → make → make install)
        │
        ▼
5. Configure the PATH so the "amk" commands work from any folder
        │
        ▼
6. (Optional) High-level backends: ORCA and/or MACE/UMA models
```

Step 7 (ORCA, MACE, UMA) is **only needed if you're going to run
high-level (HL) calculations**. By default, AutoMeKin already ships
with MOPAC for exploring reactions at low level (LL), so it can be
installed without this extra step and added later whenever it's
needed — without having to recompile anything.

## Step 1 — System dependencies <a name="step-1"></a>

AutoMeKin needs build tools (C, Fortran), shell utilities and an
SQLite database.

**Optional: check what's already installed.** Many of these come
preinstalled on Ubuntu, or may already be present from other projects.
This just prints `OK` or `MISSING` for each one — nothing gets changed:

```bash
for pkg in git curl build-essential gfortran autoconf automake gawk bc \
           environment-modules parallel sqlite3 libsqlite3-dev; do
  dpkg -s "$pkg" &>/dev/null && echo "OK      $pkg" || echo "MISSING $pkg"
done
```

This step can be skipped — the install command below is safe to run
regardless, since `apt` simply skips whatever is already installed:

```bash
sudo apt update
sudo apt install -y \
  git curl \
  build-essential gfortran \
  autoconf automake \
  gawk bc \
  environment-modules \
  parallel \
  sqlite3 libsqlite3-dev
```

**What does each group install?**

| Package(s) | What it's for |
|---|---|
| `git`, `curl` | Download the source code and auxiliary files |
| `build-essential`, `gfortran` | C/C++ and Fortran compilers (AutoMeKin has code in both languages) |
| `autoconf`, `automake` | Generate the `configure` script from the source code |
| `gawk`, `bc` | Text and calculation utilities used by internal scripts |
| `environment-modules` | Lets you load/unload AutoMeKin as a "module" (optional but recommended) |
| `parallel` | Runs several calculations in parallel (speeds up simulations) |
| `sqlite3`, `libsqlite3-dev` | Database where AutoMeKin stores intermediate results |

## Step 2 — Python with Miniconda <a name="step-2"></a>

AutoMeKin uses several scientific Python libraries (ASE, NumPy, SciPy,
NetworkX, Matplotlib). The cleanest way to install them without
interfering with the system Python is to create a dedicated **conda
environment**.

### 2.1 Install Miniconda (if not already present)

```bash
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

Accept the license, and when prompted, let the installer initialize
conda in the shell. Close and reopen the terminal (or run
`source ~/.bashrc`) so the `conda` command becomes available.

{: .note }
If Miniconda or Anaconda is already installed, this step can be skipped.

### 2.2 Create the environment for AutoMeKin

```bash
conda create -n amk_env python=3.11 -y
conda activate amk_env
```

{: .note }
If this fails complaining about the Terms of Service for the
`pkgs/main`/`pkgs/r` channels not being accepted, run these two
commands (the error message itself says the same thing) and then retry
`conda create`. This is a one-time Anaconda requirement, unrelated to
AutoMeKin itself.

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

### 2.3 Install the required libraries

```bash
conda install -y -c conda-forge numpy scipy matplotlib networkx sqlite joblib
pip install ase
```

Verify everything installed correctly:

```bash
python3 -c "import ase, numpy, scipy, networkx, matplotlib, joblib; print('All good')"
```

It should print `All good` with no errors.

{: .important }
Every time a new terminal is opened to build or run AutoMeKin,
activate the environment first with `conda activate amk_env`.

## Step 3 — Download the source code <a name="step-3"></a>

With the `amk_env` environment activated, pick a folder for the
project (for example, the home folder) and clone the repository:

```bash
mkdir -p ~/automekin
cd ~/automekin
git clone https://github.com/ComputationalChem-USC/AutoMeKin-X.git src
cd src
```

This creates `~/automekin/src` with all the source code.

## Step 4 — Build and install AutoMeKin <a name="step-4"></a>

This is the actual "compilation" step. It follows the standard GNU
toolchain flow: `autoreconf` → `configure` → `make` → `make install`.

From `~/automekin/src`:

```bash
autoreconf -i
./configure --prefix=$HOME/automekin/install
make
make install
```

**What does each command do?**

- `autoreconf -i` — generates the `configure` script from the
  project's templates (also installs any missing auxiliary files).
- `./configure --prefix=...` — checks that all dependencies are
  present and prepares the build to install into the folder given by
  `--prefix` (here, `~/automekin/install`). **Check the summary it
  prints at the end**: if something is missing, it will say so
  explicitly.
- `make` — compiles the code (takes a few minutes).
- `make install` — copies the compiled binaries, scripts and modules
  to `~/automekin/install`.

If `make` fails because a package is missing, go back to
[Step 1](#step-1), install what's missing, and repeat `./configure`
and `make` (no need to repeat `autoreconf`).

## Step 5 — Set up the environment permanently <a name="step-5"></a>

To be able to run AutoMeKin's commands from any folder, in any new
terminal, add the following to the end of `~/.bashrc`:

```bash
# --- AutoMeKin ---
module use $HOME/automekin/install/modules
export AMK=$HOME/automekin/install
export PATH=$AMK/bin:$AMK/bin/HLscripts:$AMK/bin/MOPAC_DEV:$PATH
export LIBRARY_PATH=$AMK/lib:$AMK/bin/MOPAC_DEV
```

This can be added by editing the file directly, or with this command
(careful: use `>>` to **append**, not `>`, which would erase the
file):

```bash
cat >> ~/.bashrc << 'EOF'

# --- AutoMeKin ---
module use $HOME/automekin/install/modules
export AMK=$HOME/automekin/install
export PATH=$AMK/bin:$AMK/bin/HLscripts:$AMK/bin/MOPAC_DEV:$PATH
export LIBRARY_PATH=$AMK/lib:$AMK/bin/MOPAC_DEV
EOF
```

Then apply the changes:

```bash
source ~/.bashrc
```

{: .note }
Since `amk_env` is also in use, remember that both `conda activate
amk_env` (for the Python libraries) and this `~/.bashrc` block (to
find commands like `amk.sh`) are needed in every new terminal. To have
the conda environment activate automatically, `conda activate amk_env`
can also be added to the end of `~/.bashrc`, though it's not required.

## Step 6 — Verify that everything works <a name="step-6"></a>

Open a new terminal (so the `.bashrc` changes take effect), activate
the environment, and check that the main command responds:

```bash
conda activate amk_env
amk.sh
```

If everything is installed correctly, AutoMeKin's ASCII logo appears,
followed by a message like this:

```
One argument is required
Execute this script as in this example:
  amk.sh amk.dat
where amk.dat is the inputfile
```

<p align="center">
   <img src="{{ "/assets/images/beginners_tutorial/banner.png" | relative_url }}" alt="AutoMeKin ASCII logo banner" width="700">
</p>

This message **confirms the installation worked**: the program runs,
recognizes its dependencies, and is only complaining that no input
file was given (covered in the [next page](beginners_lowlevel.html)).

As an extra check, AutoMeKin ships with a test suite that runs a real
case end to end:

```bash
cd $AMK/../src   # or the folder where the repo was cloned
run_test.sh --tests=FA
```

`FA` is the reference example (formic acid) used to validate that the
whole calculation chain works correctly. At this point, before
Step 7 below, the results obtained will be **low-level (LL) only**.

## Step 7 — (Optional) High-level backends: ORCA, MACE and UMA <a name="step-7"></a>

### 7.1 What are LL and HL, and when is this step needed?

AutoMeKin works at two levels:

- **LL (Low Level):** fast but less accurate. Used to explore a huge
  number of possible reactions. It uses **MOPAC** by default, which is
  already included — nothing extra needs to be installed for this.
- **HL (High Level):** more accurate but much more expensive. Used to
  refine only the most promising results found at LL.

If the input file (covered on the next page) is going to use the
`HighLevel` keyword with something other than MOPAC, the corresponding
engine needs to be installed. AutoMeKin supports several backends for
HL:

| Backend | `HighLevel` keyword | What needs to be installed |
|---|---|---|
| Gaussian 09/16 | `g09` / `g16` | A Gaussian license (not covered here) |
| **ORCA** | `orca` | Free download for academic use ([8.2](#72-orca)) |
| Entos Qcore | `qcore` | conda package `qcore` (see the repository's `automekin.yml` for a specific version) |
| **MLIP: MACE** | `mlip mace` | Python libraries + the `MACE-omol-0-extra-large-1024.model` model ([7.3](#73-mlip)) |
| **MLIP: UMA** | `mlip uma` | Python libraries + the `uma-m-1p1.pt` model ([7.3](#73-mlip)) |

This section covers **ORCA** and the **MLIP models (MACE and UMA)**,
the most common, freely/openly accessible options.

{: .note }
Only one of the three needs to be installed (e.g. only ORCA, or only
MACE) — there's no need to install all of them unless all are going to
be used.

### 7.2 ORCA

[ORCA](https://www.faccts.de/orca/) is a free-for-academic-use quantum
chemistry program, but **it's not a simple `curl` or `apt` download**:
it requires registering on its official forum and accepting the
license.

**1. Create an account and request the download**

- Register at <https://orcaforum.kofo.mpg.de/index.php?register/>.

  <p align="center">
     <img src="{{ "/assets/images/beginners_tutorial/register_orca.png" | relative_url }}" alt="ORCA forum registration page" width="700">
  </p>

- Confirm the email and accept the EULA (license agreement).

  <p align="center">
     <img src="{{ "/assets/images/beginners_tutorial/agreement.png" | relative_url }}" alt="ORCA EULA agreement" width="700">
  </p>

- Log in and go to the *Filebase* section. Choose the **Linux x86-64**
  build, **"shared, OpenMPI"** variant (matching the target
  distribution; on Ubuntu 22.04 the build against OpenMPI 4.1 is
  used), and download the `.tar.xz` archive.

  <p align="center">
     <img src="{{ "/assets/images/beginners_tutorial/download.png" | relative_url }}" alt="ORCA Filebase download section" width="700">
  </p>

**2. Install OpenMPI 4.1 (a required ORCA dependency)**

ORCA doesn't bundle OpenMPI — it needs to find it on the `PATH`.

```bash
sudo apt install -y openmpi-bin libopenmpi-dev
mpirun --version
```

**3. Extract ORCA**

The downloaded `.tar.xz` (typically in the Downloads folder) can be
extracted wherever the program should live, for example:

```bash
mkdir -p ~/orca6
tar xf ~/Downloads/orca_6_*_linux_x86-64_shared_openmpi*.tar.xz -C ~/orca6
```

**4. Add it to the PATH**

```bash
cat >> ~/.bashrc << 'EOF'

# --- ORCA ---
export PATH="$HOME/orca6/orca6/bin:$PATH"
EOF
source ~/.bashrc
```

(Adjust the `~/orca6/orca6` path to whatever folder name was actually
created when extracting the tarball — it usually includes the version
number.)

**5. Verify**

```bash
orca
```

This should print the ORCA banner. If `orca: command not found`
appears instead, check that the PATH entry points to the folder that
actually contains the `orca` executable. Depending on the ORCA
version, this may or may not be inside a `bin/` subfolder — some
versions install the executable directly in the extracted folder, in
which case the PATH entry should point there instead, e.g.
`export PATH="$HOME/orca6/orca6:$PATH"`.

### 7.3 Machine-learning interatomic potentials (MLIP): MACE and UMA <a name="73-mlip"></a>

MACE and UMA are **machine-learning models** that replace a
traditional quantum chemistry program for the HL step. With them,
Gaussian or ORCA are not needed: AutoMeKin calls the model directly.

**1. Install the required Python libraries**

With the `amk_env` environment activated (`conda activate amk_env`),
install them in **two separate `pip install` commands, in this exact
order** — not all in one command:

```bash
pip install torch sella omegaconf fairchem-core
pip install mace-torch

# PyTorch >=2.6 needs this to load a file e3nn ships with itself
# (harmless to run even if the e3nn build doesn't need it -- it's a no-op then)
E3NN_WIGNER=$(python3 -c "import e3nn, os; print(os.path.join(os.path.dirname(e3nn.__file__), 'o3', '_wigner.py'))")
sed -i "s/'constants.pt'))/'constants.pt'), weights_only=False)/" "$E3NN_WIGNER"

# Avoids a JIT-compile crash on older g++ when UMA first runs
# (also harmless if the compiler is fine -- just skips that speed optimization)
echo 'export TORCHDYNAMO_DISABLE=1' >> ~/.bashrc
export TORCHDYNAMO_DISABLE=1
```

{: .note }
**Why two commands?** `mace-torch` requires an exact version,
`e3nn==0.4.4`, while `fairchem-core` requires `e3nn>=0.5`. Those two
constraints can't both be satisfied at once, so asking `pip` to
install all five packages together in a single command fails with a
`ResolutionImpossible` error. Installing `fairchem-core` first and
`mace-torch` second sidesteps this: `pip` installs `e3nn>=0.5` for
`fairchem-core`, then the second command quietly downgrades it to
`e3nn==0.4.4` for `mace-torch`. A warning like `fairchem-core 2.20.0
requires e3nn>=0.5, but you have e3nn 0.4.4 which is incompatible` is
expected at the end of the second command, and is safe to ignore —
AutoMeKin only uses the parts of `fairchem-core` that work fine with
`e3nn 0.4.4`.

If an NVIDIA GPU is available, install the CUDA-enabled `torch` build
matching the driver first, following the instructions at
[pytorch.org](https://pytorch.org/get-started/locally/), then run the
two commands above (they'll reuse the `torch` already installed).
Without a GPU, the standard `pip install torch` works fine too, it
just runs on CPU.

**2. Create the models folder**

AutoMeKin looks for models in a fixed path inside the installation,
`$AMK/models/` (this is not configurable from the input file):

```bash
mkdir -p $AMK/models
```

**3. Download the MACE model**

The `MACE-omol-0-extra-large-1024.model` model (~400 MB, ASL academic
license) can be downloaded directly, with no account required, from
the GitHub releases:

```bash
wget -O $AMK/models/MACE-omol-0-extra-large-1024.model \
  https://github.com/ACEsuit/mace-foundations/releases/download/mace_omol_0/MACE-omol-0-extra-large-1024.model
```

**4. Download the UMA model**

The `uma-m-1p1.pt` model (~11 GB) is hosted on Hugging Face and
**requires accepting a license** before it can be downloaded:

- Create an account at <https://huggingface.co/join> if needed.

  <p align="center">
     <img src="{{ "/assets/images/beginners_tutorial/Hugging_face_login.png" | relative_url }}" alt="Hugging Face login page" width="700">
  </p>

- Go to <https://huggingface.co/facebook/UMA> and accept the "FAIR
  Chemistry License v1" (it will ask for a full legal name, date of
  birth, and organization).

  <p align="center">
     <img src="{{ "/assets/images/beginners_tutorial/license_agreement.png" | relative_url }}" alt="FAIR Chemistry License agreement" width="700">
  </p>

  {: .note }
  Approval for the request usually takes a few minutes. Once accepted,
  an email granting access to the UMA models arrives, like this one:

  <p align="center">
     <img src="{{ "/assets/images/beginners_tutorial/acceso.png" | relative_url }}" alt="UMA access approval email" width="700">
  </p>

- Generate an access token at
  <https://huggingface.co/settings/tokens> (a read-only one is
  enough).

  <p align="center">
     <img src="{{ "/assets/images/beginners_tutorial/token.png" | relative_url }}" alt="Hugging Face access token generation" width="700">
  </p>

Once the account is approved, install the client and authenticate:

```bash
pip install -U huggingface_hub
hf auth login
# Paste the token here when prompted
```

<p align="center">
   <img src="{{ "/assets/images/beginners_tutorial/hf_login.png" | relative_url }}" alt="Hugging Face CLI login" width="700">
</p>

Download the model, then move it out of the `checkpoints/` subfolder
that `--local-dir` recreates (same reason as the atom-refs file below
— `--local-dir` preserves the repository's internal folder structure):

```bash
hf download facebook/UMA checkpoints/uma-m-1p1.pt \
  --local-dir $AMK/models
mv $AMK/models/checkpoints/uma-m-1p1.pt $AMK/models/uma-m-1p1.pt
rmdir $AMK/models/checkpoints
```

(Use `huggingface-cli download ...` instead of `hf download ...` on an
older `huggingface_hub` version without the `hf` command.)

This can take a while given the file size (11 GB).

The optional atom-reference file — recommended because it improves
accuracy for single-atom fragments — lives in the same repository
under `references/iso_atom_elem_refs.yaml`, not at the repository
root, and under a different name than the one AutoMeKin expects.
Download it and rename it in one go:

```bash
hf download facebook/UMA references/iso_atom_elem_refs.yaml \
  --local-dir $AMK/models
mv $AMK/models/references/iso_atom_elem_refs.yaml \
  $AMK/models/uma-m-1p1_atom_refs.yaml
rmdir $AMK/models/references
```

`--local-dir` preserves the repository's folder structure, so the
file first lands at
`$AMK/models/references/iso_atom_elem_refs.yaml` — the `mv` puts it
directly in `$AMK/models/` under the exact name AutoMeKin looks for.

{: .warning }
AutoMeKin looks for models by their **exact file name**
(`MACE-omol-0-extra-large-1024.model`, `uma-m-1p1.pt`,
`uma-m-1p1_atom_refs.yaml`). If the name doesn't match, the
calculation fails with an error like `MLIP model file not found: ...`.
The commands above already save the file with the correct name; when
downloading manually from a browser, double-check it wasn't saved
with a suffix like `(1)`.

**5. Verify where the models ended up**

```bash
ls -lh $AMK/models
```

The `.model` / `.pt` / `.yaml` files downloaded above should appear.

With this in place, the input file can use `HighLevel mlip mace` or
`HighLevel mlip uma`.

## Common troubleshooting <a name="troubleshooting"></a>

| Symptom | Likely cause | Fix |
|---|---|---|
| `amk.sh: command not found` | The Step 5 block isn't in `~/.bashrc`, or a new terminal wasn't opened | Check `~/.bashrc` and run `source ~/.bashrc` |
| `configure: error: ...` mentioning a package | A system dependency is missing | Go back to [Step 1](#step-1) and install the package it names |
| `ModuleNotFoundError` in Python | The conda environment isn't activated, or a library is missing | `conda activate amk_env` and redo Step 2.3 |
| `make` fails partway through | Usually an incomplete `configure` | Delete the `src` folder, clone it again, and redo Step 4 from scratch |
| Permission denied installing packages with `apt` | Missing `sudo` | Add `sudo` before the `apt install` command |
| `orca: command not found` | ORCA's `bin` folder isn't on the `PATH`, or a new terminal wasn't opened | Check the `# --- ORCA ---` block in `~/.bashrc` and run `source ~/.bashrc` |
| ORCA hangs or won't run in parallel | Missing OpenMPI 4.1, or a version mismatch | `sudo apt install -y openmpi-bin libopenmpi-dev` and confirm with `mpirun --version` |
| `huggingface-cli` says "deprecated and no longer works" | `huggingface_hub` 1.0+ is installed, which renamed the CLI | Use `hf auth login` / `hf download ...` instead |
| `403 Forbidden` downloading the UMA model | The license on the model page hasn't been accepted, or authentication (`hf auth login`) is missing | Go to <https://huggingface.co/facebook/UMA>, accept the license, and re-authenticate |
| `pip` fails with `ResolutionImpossible` mentioning `e3nn` | `mace-torch` and `fairchem-core` were installed in the same `pip install` command — their `e3nn` version requirements conflict | Install them separately: `pip install torch sella omegaconf fairchem-core`, then `pip install mace-torch` (see [7.3](#73-mlip)) |
| `MLIP model file not found: ...` when launching a run | The model isn't in `$AMK/models/`, or the file name doesn't match exactly | Run `ls -lh $AMK/models` and compare the name against the table in [7.3](#73-mlip) |
| UMA download is very slow or gets interrupted | 11 GB file, sensitive to unstable connections | Re-run the same `hf download` (or `huggingface-cli download`) command: it resumes instead of starting over |

## What's next <a name="whats-next"></a>

With this, AutoMeKin is installed and verified. The [next
page](beginners_lowlevel.html) covers how to actually use it, from
zero: preparing a starting molecular structure, writing an input file,
launching a first real calculation, and reading the results.
