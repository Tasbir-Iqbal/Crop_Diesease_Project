from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps
import hashlib
import random
import shutil
import tempfile

SOURCE = Path(r"D:\Project\dataset")
DESTINATION = SOURCE.parent / "dataset_augmented"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
SEED = 42


def image_files(folder):
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONS
    )


def class_folders(split):
    folder = SOURCE / split
    if not folder.is_dir():
        raise FileNotFoundError(f"Missing folder: {folder}")
    return {p.name: p for p in folder.iterdir() if p.is_dir()}


def create_variants(image, rng):
    mirrored = ImageOps.mirror(image)
    mirrored = ImageEnhance.Brightness(mirrored).enhance(rng.uniform(0.90, 1.10))

    width, height = image.size
    scale = rng.uniform(0.96, 0.99)
    crop_width = max(1, int(width * scale))
    crop_height = max(1, int(height * scale))
    left = rng.randint(0, width - crop_width)
    top = rng.randint(0, height - crop_height)
    cropped = image.crop((left, top, left + crop_width, top + crop_height))
    cropped = cropped.resize(image.size, Image.Resampling.BICUBIC)
    cropped = ImageEnhance.Contrast(cropped).enhance(rng.uniform(0.95, 1.05))
    return mirrored, cropped


def main():
    train_classes = class_folders("train")
    val_classes = class_folders("val")
    if not train_classes or set(train_classes) != set(val_classes):
        raise ValueError("train and val must contain the same nonempty class-folder names.")
    if DESTINATION.exists():
        raise FileExistsError(
            f"{DESTINATION} already exists. Nothing was changed. "
            "Rename it before running again."
        )
    if not any(image_files(folder) for folder in train_classes.values()):
        raise ValueError("No training images found under train/<class_name>/.")

    rng = random.Random(SEED)
    temporary = Path(tempfile.mkdtemp(prefix=".fieldscan_aug_", dir=SOURCE.parent))
    originals = 0
    generated = 0
    validation = 0
    try:
        for class_name in sorted(train_classes):
            images = image_files(train_classes[class_name])
            if not images:
                raise ValueError(f"No training images in class: {class_name}")
            output = temporary / "train" / class_name
            output.mkdir(parents=True)
            for path in images:
                with Image.open(path) as opened:
                    image = ImageOps.exif_transpose(opened).convert("RGB")
                shutil.copy2(path, output / path.name)
                originals += 1
                token = hashlib.sha256(path.name.encode("utf-8")).hexdigest()[:12]
                for index, variant in enumerate(create_variants(image, rng), start=1):
                    variant.save(output / f"{path.stem}__aug_{token}_{index}.jpg", quality=92)
                    generated += 1

            val_images = image_files(val_classes[class_name])
            if not val_images:
                raise ValueError(f"No validation images in class: {class_name}")
            val_output = temporary / "val" / class_name
            val_output.mkdir(parents=True)
            for path in val_images:
                shutil.copy2(path, val_output / path.name)
                validation += 1
            print(f"{class_name}: {len(images)} originals, {2 * len(images)} augmented, {len(val_images)} validation")

        temporary.rename(DESTINATION)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    print(f"\nDone. Output: {DESTINATION}")
    print(f"Training: {originals} originals + {generated} new images")
    print(f"Validation: {validation} unchanged copies")
    print("Your original dataset and Flask application were not modified.")
    print("The new dataset will not affect predictions until you train and select new model weights.")


if __name__ == "__main__":
    main()
