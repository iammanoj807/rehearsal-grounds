"""Step 06: learned image embedding of every patch with a pretrained ResNet-18.

Each patch becomes a 3-channel image: hillshade (azimuth 315, altitude 45),
slope / 45 degrees (clipped to 1), and plane-detrended elevation scaled to
0-1 within the patch. Images are resized to 224 x 224, ImageNet-normalised and
passed through ``torchvision.models.resnet18(weights="IMAGENET1K_V1")`` with
the final layer removed, giving 512 numbers per patch.

Target patches and crater-centred benchmark patches are also embedded at 90,
180 and 270 degrees, so queries can take the best rotation (orientation is
arbitrary across bodies).

The 512-d vectors are L2-normalised and reduced to 64-d with PCA fitted on
Earth patches only.

Outputs: ``work/index/embeddings.npy`` (n x 64, rows aligned with
``features.parquet``), ``work/index/embeddings_rot.npy`` (m x 4 x 64) with
``embeddings_rot_rows.npy`` (the m row numbers), and ``work/index/pca.joblib``.
"""

from __future__ import annotations

import sys

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.decomposition import PCA
from torchvision.models import ResNet18_Weights, resnet18

from common import get_logger, index_dir, load_config, patches_dir, run_dir
from features import detrended_unit, fill_gaps, hillshade, slope_deg

log = get_logger("06_embed")
IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
BATCH = 256


def patch_image(z: np.ndarray, res: float) -> np.ndarray:
    """3 x P x P float32 image: hillshade, slope/45, detrended elevation."""
    z = fill_gaps(z)
    return np.stack([
        hillshade(z, res),
        np.clip(slope_deg(z, res) / 45.0, 0.0, 1.0),
        detrended_unit(z),
    ]).astype(np.float32)


def pick_device() -> torch.device:
    """Apple GPU (MPS) or CUDA when available, otherwise CPU."""
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def build_model(device: torch.device) -> torch.nn.Module:
    """ResNet-18 with ImageNet weights and the classifier removed."""
    model = resnet18(weights=ResNet18_Weights.IMAGENET1K_V1)
    model.fc = torch.nn.Identity()
    return model.eval().to(device)


@torch.no_grad()
def embed_images(model: torch.nn.Module, images: np.ndarray, device: torch.device) -> np.ndarray:
    """512-d embeddings for an (n, 3, P, P) image stack."""
    out = []
    for start in range(0, len(images), BATCH):
        batch = torch.from_numpy(images[start:start + BATCH])
        batch = F.interpolate(batch, size=(224, 224), mode="bilinear", align_corners=False)
        batch = (batch - IMAGENET_MEAN) / IMAGENET_STD
        out.append(model(batch.to(device)).float().cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, 512), np.float32)


def l2n(x: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalisation."""
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12)


def main() -> int:
    """Embed all patches, fit PCA on Earth, write the embedding files."""
    cfg = load_config()
    res = float(cfg["resolution_m"])
    torch.manual_seed(int(cfg["seed"]))
    feats = pd.read_parquet(run_dir() / "features.parquet")
    device = pick_device()
    model = build_model(device)
    log.info("device %s; embedding %d patches", device, len(feats))

    raw = np.zeros((len(feats), 512), np.float32)
    rot_rows: list[int] = []
    rot_raw: list[np.ndarray] = []
    row_offset = 0
    for sid, group in feats.groupby("source_id", sort=False):
        arrays = np.load(patches_dir() / f"{sid}.npy")
        if len(arrays) != len(group):
            raise RuntimeError(f"{sid}: {len(arrays)} arrays vs {len(group)} rows")
        rows = group.index.to_numpy()
        images = np.stack([patch_image(z, res) for z in arrays])
        raw[rows] = embed_images(model, images, device)
        needs_rot = (group["body"] != "earth").to_numpy() | (group["crater_centre_of"].fillna("") != "").to_numpy()
        if needs_rot.any():
            sel = np.flatnonzero(needs_rot)
            rots = [raw[rows[sel]]]
            for k in (1, 2, 3):
                rot_imgs = np.stack([patch_image(np.rot90(arrays[i], k), res) for i in sel])
                rots.append(embed_images(model, rot_imgs, device))
            rot_raw.append(np.stack(rots, axis=1))
            rot_rows.extend(rows[sel].tolist())
        row_offset += len(group)
        log.info("%s: %d patches embedded%s", sid, len(group),
                 f" (+{int(needs_rot.sum())} x 3 rotations)" if needs_rot.any() else "")

    earth = (feats["body"] == "earth").to_numpy()
    pca = PCA(n_components=64, random_state=int(cfg["seed"]))
    pca.fit(l2n(raw[earth]))
    emb = pca.transform(l2n(raw)).astype(np.float32)
    rot = np.stack([pca.transform(l2n(r)) for r in np.concatenate(rot_raw).transpose(1, 0, 2)], axis=1).astype(np.float32)
    out = index_dir()
    np.save(out / "embeddings.npy", emb)
    np.save(out / "embeddings_rot.npy", rot)
    np.save(out / "embeddings_rot_rows.npy", np.asarray(rot_rows, dtype=np.int64))
    joblib.dump(pca, out / "pca.joblib")
    log.info("PCA 512->64 keeps %.1f%% of variance; %d rotation sets", 100 * pca.explained_variance_ratio_.sum(), len(rot_rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
