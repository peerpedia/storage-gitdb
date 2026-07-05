# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""Centralised filesystem paths for the gitdb backend.

Override the data root by setting the ``PEERPEDIA_HOME`` environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_ROOT = Path(os.environ.get("PEERPEDIA_HOME", Path.home() / ".peerpedia"))
ARTICLES_DIR = DATA_ROOT / "articles"
DB_PATH = DATA_ROOT / "peerpedia.db"
DB_URL = f"sqlite:///{DB_PATH}"
