from pathlib import Path

from rest_framework import serializers

MAX_PRODUCT_IMAGE_BYTES = 2 * 1024 * 1024

IMAGE_FORMATS = {
    ".jpg": ("image/jpeg", b"\xff\xd8\xff"),
    ".jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    ".png": ("image/png", b"\x89PNG\r\n\x1a\n"),
    ".webp": ("image/webp", b"WEBP"),
}

ALLOWED_MIME_TYPES = frozenset({mime for mime, _ in IMAGE_FORMATS.values()})


def product_image_content_type(filename):
    """Retourne le type MIME autorisé pour un nom de fichier d'image produit."""
    extension = Path(str(filename).replace("\\", "/")).suffix.lower()
    metadata = IMAGE_FORMATS.get(extension)
    return metadata[0] if metadata else "application/octet-stream"


def validate_product_image_file(image):
    """Valide extension, MIME déclaré, signature binaire et taille d'une image produit."""
    if not image:
        raise serializers.ValidationError("Un fichier image est requis.")

    if image.size > MAX_PRODUCT_IMAGE_BYTES:
        raise serializers.ValidationError("L’image ne peut pas dépasser 2 Mo.")

    extension = Path(str(image.name).replace("\\", "/")).suffix.lower()
    metadata = IMAGE_FORMATS.get(extension)
    if not metadata:
        raise serializers.ValidationError("L’image doit être un fichier JPEG, PNG ou WebP.")

    expected_mime, signature = metadata
    declared_mime = (getattr(image, "content_type", "") or "").lower()
    if declared_mime and declared_mime not in ALLOWED_MIME_TYPES:
        raise serializers.ValidationError("Le type MIME déclaré n’est pas une image autorisée.")
    if declared_mime and declared_mime != expected_mime:
        raise serializers.ValidationError("Le type MIME déclaré ne correspond pas à l’extension du fichier.")

    header = image.read(max(12, len(signature) + 8))
    image.seek(0)
    if extension == ".webp":
        valid_signature = header[:4] == b"RIFF" and header[8:12] == signature
    else:
        valid_signature = header.startswith(signature)
    if not valid_signature:
        raise serializers.ValidationError("La signature du fichier ne correspond pas à une image autorisée.")

    return image
