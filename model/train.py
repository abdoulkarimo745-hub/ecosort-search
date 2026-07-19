"""Script d'entraînement du modèle EcoSort / EcoSort-Search — Jalon 1.

Entraîne un classifieur d'images par transfer learning (MobileNetV2) sur le
dataset Kaggle "Garbage Classification" :
https://www.kaggle.com/code/muhammedabdulazeem/garbage-classification

Le dataset attendu est un dossier contenant une sous-dossier par matière :

    dataset/
      cardboard/
      glass/
      metal/
      paper/
      plastic/
      trash/

Usage :

    python model/train.py --data-dir chemin/vers/dataset

Options utiles :

    --epochs 15          nombre d'époques (défaut : 15)
    --batch-size 16       taille de batch (défaut : 16, réduit pour limiter
                          la mémoire utilisée sur un PC peu puissant)
    --img-size 160        image carrée redimensionnée à IMG_SIZE x IMG_SIZE
    --output model/modele_eco_sort.h5   fichier modèle produit
    --fine-tune           dégèle les dernières couches de MobileNetV2 pour un
                          second passage d'entraînement (meilleure précision,
                          plus lent)

Le script produit :
  - le modèle entraîné (fichier .h5, voir --output)
  - model/class_names.json : ordre des classes utilisé par le modèle, pour que
    model/predict.py puisse retrouver le nom de matière correspondant à
    chaque indice de sortie.
"""
import argparse
import atexit
import json
import os
import shutil
import tempfile

# Réduit le bruit des logs TensorFlow (à faire avant l'import de tensorflow).
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(MODEL_DIR, "modele_eco_sort.h5")
DEFAULT_CLASS_NAMES_PATH = os.path.join(MODEL_DIR, "class_names.json")


def parse_args():
    parser = argparse.ArgumentParser(description="Entraîne le modèle EcoSort-Search (tri des déchets).")
    parser.add_argument("--data-dir", default="dataset", help="Dossier du dataset (un sous-dossier par classe).")
    parser.add_argument("--epochs", type=int, default=15, help="Nombre d'époques d'entraînement.")
    parser.add_argument("--batch-size", type=int, default=16, help="Taille de batch.")
    parser.add_argument("--img-size", type=int, default=160, help="Taille (carrée) des images en entrée.")
    parser.add_argument("--val-split", type=float, default=0.2, help="Proportion des données pour la validation.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Chemin du modèle entraîné à sauvegarder (.h5).")
    parser.add_argument(
        "--fine-tune",
        action="store_true",
        help="Dégèle les dernières couches de MobileNetV2 pour un second passage d'entraînement.",
    )
    return parser.parse_args()


def build_model(num_classes, img_size):
    import tensorflow as tf
    from tensorflow.keras import layers, models
    from tensorflow.keras.applications import MobileNetV2

    base_model = MobileNetV2(
        input_shape=(img_size, img_size, 3),
        include_top=False,
        weights="imagenet",
    )
    base_model.trainable = False

    data_augmentation = tf.keras.Sequential(
        [
            layers.RandomFlip("horizontal"),
            layers.RandomRotation(0.1),
            layers.RandomZoom(0.1),
        ],
        name="augmentation",
    )

    inputs = tf.keras.Input(shape=(img_size, img_size, 3))
    x = data_augmentation(inputs)
    # Équivalent exact de mobilenet_v2.preprocess_input (x/127.5 - 1), mais
    # avec une couche Keras standard (Rescaling) plutôt qu'un Lambda autour
    # d'une fonction externe : un Lambda(preprocess_input) échoue à se
    # recharger avec Keras 3 (TypeError "Could not locate function
    # 'preprocess_input'" au chargement), alors que Rescaling se sérialise et
    # se recharge sans problème dans model/predict.py.
    x = layers.Rescaling(scale=1.0 / 127.5, offset=-1.0)(x)
    x = base_model(x, training=False)
    x = layers.GlobalAveragePooling2D()(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(num_classes, activation="softmax")(x)
    model = models.Model(inputs, outputs)
    return model, base_model


def main():
    args = parse_args()

    if not os.path.isdir(args.data_dir):
        raise SystemExit(
            f"Dossier dataset introuvable : '{args.data_dir}'.\n"
            "Télécharge le dataset Kaggle 'Garbage Classification' et indique son "
            "chemin avec --data-dir (voir le docstring en tête de ce fichier)."
        )

    import tensorflow as tf

    img_size = args.img_size

    train_ds = tf.keras.utils.image_dataset_from_directory(
        args.data_dir,
        validation_split=args.val_split,
        subset="training",
        seed=123,
        image_size=(img_size, img_size),
        batch_size=args.batch_size,
    )
    val_ds = tf.keras.utils.image_dataset_from_directory(
        args.data_dir,
        validation_split=args.val_split,
        subset="validation",
        seed=123,
        image_size=(img_size, img_size),
        batch_size=args.batch_size,
    )

    class_names = train_ds.class_names
    print(f"Classes détectées ({len(class_names)}) : {class_names}")

    AUTOTUNE = tf.data.AUTOTUNE
    # Cache sur DISQUE plutôt qu'en RAM : .cache() sans argument garde toutes
    # les images décodées en mémoire vive pendant toute la durée de
    # l'entraînement (~1 Go+ avec ce dataset), ce qui peut faire tuer le
    # processus silencieusement par l'OS sur un PC avec peu de RAM libre
    # (symptôme : le script s'arrête sans traceback ni message d'erreur).
    # Le cache disque est un peu plus lent mais beaucoup plus sûr.
    cache_dir = tempfile.mkdtemp(prefix="ecosort_train_cache_")
    atexit.register(shutil.rmtree, cache_dir, ignore_errors=True)
    train_ds = train_ds.cache(os.path.join(cache_dir, "train")).prefetch(buffer_size=AUTOTUNE)
    val_ds = val_ds.cache(os.path.join(cache_dir, "val")).prefetch(buffer_size=AUTOTUNE)

    model, base_model = build_model(len(class_names), img_size)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.summary()

    early_stopping = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=3, restore_best_weights=True
    )

    print("\n--- Entraînement de la tête de classification ---")
    model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=args.epochs,
        callbacks=[early_stopping],
    )

    if args.fine_tune:
        print("\n--- Fine-tuning des dernières couches de MobileNetV2 ---")
        base_model.trainable = True
        # Ne dégèle que la seconde moitié du réseau pour limiter l'overfitting.
        for layer in base_model.layers[: len(base_model.layers) // 2]:
            layer.trainable = False
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=1e-5),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )
        model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=max(args.epochs // 3, 3),
            callbacks=[early_stopping],
        )

    val_loss, val_acc = model.evaluate(val_ds)
    print(f"\nPrécision finale sur le jeu de validation : {val_acc:.2%} (loss={val_loss:.4f})")

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    model.save(args.output)
    print(f"Modèle sauvegardé : {args.output}")

    with open(DEFAULT_CLASS_NAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(class_names, f, ensure_ascii=False, indent=2)
    print(f"Ordre des classes sauvegardé : {DEFAULT_CLASS_NAMES_PATH}")


if __name__ == "__main__":
    main()
