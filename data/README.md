# data/ (git-ignored)

Nothing in here is committed. Layout, identical on laptops and on the Nebius VM (`~/data`):

    data/raw/kelmarsh/      Kelmarsh_SCADA_<year>_*.zip          (scripts/download_data.sh)
    data/raw/penmanshiel/   Penmanshiel_SCADA_<year>_WT*.zip
    data/timenet/           local TimeNet registry (timenet-build output)
    data/checkpoints/       adapters / checkpoints
    data/interim/           anything preprocessing wants to cache

Set `DATA_DIR` to point elsewhere. On the VM: `export DATA_DIR=~/data`.
