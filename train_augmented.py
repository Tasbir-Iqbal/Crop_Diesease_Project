from pathlib import Path
from ultralytics import YOLO

BASE_DIR = Path(r"D:\Project")

model_path = BASE_DIR / "yolo11n-cls.pt"
dataset_path = BASE_DIR / "dataset_augmented"

model = YOLO(str(model_path))

model.train(
    data=str(dataset_path),
    epochs=60,
    imgsz=224,
    batch=16,
    patience=15,
    project=str(BASE_DIR / "runs"),
    name="classify_augmented",
    exist_ok=False,
    verbose=True,
)

print("\nAugmented training completed.")
print("New model folder:")
print(BASE_DIR / "runs" / "classify_augmented")