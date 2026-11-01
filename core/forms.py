from io import BytesIO

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, UnidentifiedImageError

from .models import Product

# a shelf photo only ever renders in a 40px tile or a 16px preview, so anything
# bigger than this is wasted bandwidth on the ledger
MAX_IMAGE_EDGE = 512
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}

# every control in the product dialog shares this shell; the padding is left
# out so a dialog can put a GH₵ prefix, an icon or a unit hint inside the field
CONTROL = (
    "w-full rounded-lg border border-slate-200 bg-slate-50 py-2 text-sm "
    "text-slate-900 transition-colors placeholder:text-slate-400 "
    "focus:border-emerald-500 focus:bg-white focus:outline-none "
    "focus:ring-2 focus:ring-emerald-500/30 dark:border-slate-700 "
    "dark:bg-slate-950 dark:text-slate-100 dark:focus:bg-slate-900"
)

PADDED = f"{CONTROL} px-3"
MONEY = f"{CONTROL} tnum pl-14 pr-3 font-semibold"
STEPPED = (
    "tnum w-full border-0 bg-transparent px-1 py-1.5 text-center text-base "
    "font-semibold text-slate-900 focus:outline-none focus:ring-0 dark:text-slate-100"
)


class ClearableImageInput(forms.ClearableFileInput):
    """A blank submit never detaches a photo (FileField.save_form_data treats
    it as "no change"), so this widget's image-clear checkbox is the only way
    to remove one. The template name is custom because the default form
    renderer resolves "django/forms/widgets/*" from Django's own pack first."""

    template_name = "core/widgets/product_image_input.html"
    clear_checkbox_label = "Remove current image"


class ProductCreationForm(forms.ModelForm):
    """price/cost drive the margin the dialog shows, so profit_rate stays out
    of the form and is written by the view."""

    class Meta:
        model = Product
        fields = (
            "name",
            "sku",
            "category",
            "stock",
            "cost",
            "price",
            "low_stock_threshold",
            "image",
        )
        # the x-model bindings belong to the add/update dialog's Alpine scope
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": PADDED,
                    "placeholder": "e.g. Radiance Vitamin C Brightening Serum (50ml)",
                    "data-autofocus": "",
                }
            ),
            "sku": forms.TextInput(
                attrs={
                    "class": f"{CONTROL} tnum uppercase pl-9 pr-3",
                    "placeholder": "NC-SK-0000",
                    "maxlength": "32",
                    "x-model": "sku",
                }
            ),
            "category": forms.Select(
                attrs={
                    "class": f"{CONTROL} appearance-none pl-3 pr-9 cursor-pointer",
                    "x-model": "cat",
                }
            ),
            "stock": forms.NumberInput(
                attrs={"class": STEPPED, "x-model": "stock"}
            ),
            "cost": forms.NumberInput(
                attrs={"class": MONEY, "step": "0.01", "x-model": "cost"}
            ),
            "price": forms.NumberInput(
                attrs={"class": MONEY, "step": "0.01", "x-model": "price"}
            ),
            "low_stock_threshold": forms.NumberInput(
                attrs={"class": f"{CONTROL} tnum pl-3 pr-16"}
            ),
            "image": ClearableImageInput(
                attrs={"class": "peer sr-only", "data-image-input": ""}
            ),
        }

    def clean_sku(self):
        """the import matches SKUs case-sensitively, so store one shape."""
        sku = (self.cleaned_data.get("sku") or "").strip().upper()
        return sku or None

    def clean_image(self):
        """Cap the upload, then shrink it: a phone photo is several megabytes
        and the biggest place it appears is a 40px ledger tile.

        None (no file submitted) must stay None so an edit without a new
        photo leaves the stored one alone; only image-clear yields False.
        """
        upload = self.cleaned_data.get("image")
        if not upload:
            return upload

        if upload.size > MAX_IMAGE_BYTES:
            raise ValidationError(
                f"Image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB. "
                "Pick a smaller file."
            )

        try:
            image = Image.open(upload)
            image.load()
        except (UnidentifiedImageError, OSError, ValueError):
            raise ValidationError("This file is not a readable image.")

        if image.format not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError(
                "Unsupported image type. Use JPG, PNG, WebP or GIF."
            )

        if max(image.size) <= MAX_IMAGE_EDGE:
            return upload

        image.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.LANCZOS)
        if image.format == "JPEG" and image.mode not in ("L", "RGB"):
            image = image.convert("RGB")

        buffer = BytesIO()
        # encoder kwargs differ per format, so only pass what each accepts
        save_options = {"quality": 88} if image.format == "JPEG" else {"optimize": True}
        if image.format == "WEBP":
            save_options = {"quality": 88, "method": 4}
        image.save(buffer, format=image.format, **save_options)
        buffer.seek(0)

        return SimpleUploadedFile(upload.name, buffer.read(), content_type=upload.content_type)
