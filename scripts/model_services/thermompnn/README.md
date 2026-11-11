# ThermoMPNN host service

Deploy the versioned runtime separately. Bind only Docker bridge 172.18.0.1:4286. Source/patches are in source-manifest.json and upstream.patch; weights are excluded from Git. Keep its dependency overlay separate from ESM and DDGun. Use OMP_NUM_THREADS=1 and MKL_NUM_THREADS=1. Verify real HTTP predictions before application switch.
