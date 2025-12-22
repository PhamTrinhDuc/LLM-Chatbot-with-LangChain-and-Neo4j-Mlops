# Install production dependencies only
```bash
uv sync --no-dev
```

# Install production + dev dependencies
```bash
uv sync
```

# Install và add dev dependency
```bash
uv add --dev pytest
```

# Remove dev dependency
```bash
uv remove --dev pytest
```

# Stop all docker container but don't remove its: 
```bash
docker stop $(docker ps -q)
```
