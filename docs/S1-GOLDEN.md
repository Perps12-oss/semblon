# S1 golden

Run `20260913T153515Z-1e915abe`.  
Pack `insightface/buffalo_l@2.0/adapter-1/sha256:20a9264f823c3c3c`.  
Windows ARM64 native. Python 3.14.4. ONNX Runtime 1.30.0. InsightFace 2.0 `buffalo_l`. CPU.

90 `.jpg` → 85 faces / 78 ok / 1 low_quality / 6 rejected.  
10 clusters / 63 clustered / 15 eligible unassigned.  
False merge 0. False splits observed (accepted).

Params frozen: `eps=0.40`, `min_samples=2`, metric `1-dot`, `STRONG_MIN_INTRA=0.50`.  
Clusters are not people. Do not retune. Do not re-ingest this dump to “improve” clustering.
