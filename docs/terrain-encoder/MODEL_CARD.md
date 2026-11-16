# Model cards

## Encoder-F and Encoder-L (not adopted)
- **Model:** ResNet-18 from ImageNet weights, with the max-pool removed for 64 px input, and a 512-d output.
- **Training:** VICReg (Lightly 1.6.1, weights 25/25/1, projector 2048-2048-2048), batch 256 half Moon / half Earth,
  AdamW 1e-3, 10-epoch warm-up, then cosine decay. Encoder-L also injects simulated lunar craters (p 0.8) into each
  view.
- **Data:** Stage 3 TRAIN patches: 162,112 Moon (SLDEM2015, LOLA 80-90 S, PGDA 78 sites) and 135,401 Earth
  (Copernicus GLO-30). Licences are in `SOURCES.md`. Hold-outs are in `PREREGISTRATION.md`.
- **Where trained:**
  - Encoder-F on the Mac: 17 epochs; best VAL epoch 11.
  - Encoder-L on the user's GPU server: 40 epochs; best VAL epoch 31.
- **Evaluation:** `RESULTS.md`. Both fail the pre-registered Stage 8 rules, so the app keeps the ImageNet
  ResNet-18.
- **Limits:**
  - Training makes the embeddings invariant to rotation, sun angle and resampling, but costs crater recognition (E2
    and E3 drop).
  - The crater benchmarks are small (7 Earth craters; 11 positive patches for E3).

## Moon-likeness (Stage 1 / Stage 7)
- **Stage 1** (ImageNet embedding): not adopted.
- **Stage 7:** with the Encoder-L embedding, the logistic arm passes the Stage 1 rule on 2 crater patches. It is held
  back pending the user's decision (see `RESULTS.md`).
