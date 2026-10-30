---
name: docker-packaging
description: Package the generated Agent into a Docker image and export a downloadable ZIP. Use after agent-testing passes.
---
# Docker Packaging

Create `project/Dockerfile` (python:3.11-slim + requirements) and `project/.dockerignore`.
Export `project/` as `m2a_project.zip` (exclude API keys, caches, and the Builder's private files).

Weight licensing: only bundle weights if the license permits redistribution
(per `LICENSE`/`model_card.md`). Otherwise omit them and note it.

Docker verification status is one of: unverified | build-ok | start-ok | test-ok | failed.
Never claim a status without a real build/start/test result. Default is **unverified**.
