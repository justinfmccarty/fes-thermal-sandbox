# Thermal Sandbox V1.0
This is the thermal sandbox codebase and application. 


## Using the application

Here's the whole thing from scratch, assuming you just opened a brand-new terminal window. You only type the lines in the code boxes.

## Step 1 — Go to the project folder

The `cd` command means "change directory" (move into a folder):

```bash
cd ~/Documents/GitHub/thermal-sandbox/treeheat
```

Everything from here on is run from inside this `treeheat` folder.

## Step 2 — Set up the environment (one time only)

`uv` is the tool that manages Python and the libraries. This command builds a private, self-contained Python environment for the project (called `.venv`). You already did this, so you can skip it — but if you ever move to a new machine, this is the command:

```bash
uv sync --extra ui --extra viz --extra radiance --extra physics --extra dev
```

Plain English: "install everything the app needs — the user interface, the plots, the raytracing engine, the physics solvers, and the dev tools." It takes a minute the first time, seconds after that.

## Step 3 — Start the app

```bash
uv run streamlit run app/streamlit_app.py
```

- `uv run` means "run this using the project's private environment" (this is why bare `streamlit` gave you *command not found* earlier — it only exists inside `.venv`).
- A browser tab opens automatically at something like `http://localhost:8501`. That tab **is** the app.
- Leave this terminal open — it's the engine running the app. Closing it stops the app.

To stop the app later: click in that terminal and press `Ctrl + C`.

## Step 4 — Use the app (four screens in the left sidebar)

1. **Setup** — point it at your project folder (the external folder you made with `treeheat init`, the one with `config/`, `inputs/`, `models/`, `outputs/`). It shows a checklist: green = ready, red = missing. Here you also pick the engine/period and save them.
2. **Guide** — the runbook (how to get files out of Grasshopper into your project). Reference only.
3. **Run** — press the launch button. It starts the simulation **in the background**, so you can close the browser tab or even refresh and it keeps going. The table shows each task as pending → running → done.
4. **Results** — once a run finishes, the plots and the scenario-comparison table appear here.

## Two things specific to your machine

Before your first **Run**, open your project's `config/config.yaml` in any text editor and make sure it has:

```yaml
simulation:
  use_accelerad: false
```

That's because the default assumes an NVIDIA GPU (Accelerad), which Macs don't have. Without this line the raytrace step errors out.

## The mental model

```
Terminal (Step 1–3)  →  starts the app engine
        │
        ▼
Browser tab (the app) →  Setup → Run → Results
        │
        ▼
Your project folder   →  inputs/ (what you provide)
                         outputs/ (what it produces)
```

So the everyday routine, once set up, is just three lines:

```bash
cd ~/Documents/GitHub/thermal-sandbox/treeheat
uv run streamlit run app/streamlit_app.py
# then work in the browser tab; press Ctrl+C in the terminal when done
```