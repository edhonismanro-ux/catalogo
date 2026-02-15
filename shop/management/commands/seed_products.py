import random
import string
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from shop.models import Product


def _rand_word(n=8):
    return "".join(random.choices(string.ascii_letters, k=n)).capitalize()


def _lorem(words=18):
    return " ".join(_rand_word(random.randint(4, 10)) for _ in range(words)) + "."


class Command(BaseCommand):
    help = "Crea productos aleatorios en shop.Product. Uso: python manage.py seed_products 30 [--clear]"

    def add_arguments(self, parser):
        parser.add_argument("count", nargs="?", type=int, default=20)
        parser.add_argument("--clear", action="store_true", help="Borra todos los productos antes de crear nuevos")

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["count"]
        clear = options["clear"]

        if clear:
            Product.objects.all().delete()
            self.stdout.write(self.style.WARNING("Productos existentes borrados."))

        created = 0
        fields = {f.name: f for f in Product._meta.get_fields()}

        # Intentamos llenar campos comunes si existen
        common = {
            "name": lambda: f"Producto {_rand_word(6)} {random.randint(10,999)}",
            "title": lambda: f"Producto {_rand_word(6)} {random.randint(10,999)}",
            "nombre": lambda: f"Producto {_rand_word(6)} {random.randint(10,999)}",
            "descripcion": lambda: _lorem(26),
            "description": lambda: _lorem(26),
            "price": lambda: Decimal(str(round(random.uniform(5, 250), 2))),
            "precio": lambda: Decimal(str(round(random.uniform(5, 250), 2))),
            "stock": lambda: random.randint(0, 80),
            "cantidad": lambda: random.randint(0, 80),
            "is_active": lambda: True,
            "activo": lambda: True,
            "created_at": lambda: timezone.now(),
        }

        for _ in range(count):
            obj = Product()

            # 1) Seteo campos “comunes”
            for fname, fn in common.items():
                if fname in fields:
                    f = fields[fname]
                    # Solo setear si no es relación y permite editar
                    if getattr(f, "editable", True) and not f.is_relation:
                        try:
                            setattr(obj, fname, fn())
                        except Exception:
                            pass

            # 2) Completar cualquier campo obligatorio que quede vacío (heurística)
            for f in Product._meta.fields:
                if f.auto_created or f.primary_key:
                    continue

                # Si ya tiene valor, saltar
                val = getattr(obj, f.name, None)
                if val not in (None, "", 0):
                    continue

                # Si permite null/blank, no es obligatorio
                if getattr(f, "null", False) or getattr(f, "blank", False):
                    continue

                # Si es FK obligatoria, intentamos agarrar el primer registro del modelo relacionado
                if f.is_relation and f.many_to_one:
                    rel_model = f.remote_field.model
                    rel_obj = rel_model.objects.first()
                    if rel_obj is not None:
                        setattr(obj, f.name, rel_obj)
                    continue

                # Tipos básicos
                try:
                    from django.db import models
                    if isinstance(f, models.CharField):
                        setattr(obj, f.name, f"{_rand_word(10)}")
                    elif isinstance(f, models.TextField):
                        setattr(obj, f.name, _lorem(30))
                    elif isinstance(f, models.IntegerField):
                        setattr(obj, f.name, random.randint(1, 100))
                    elif isinstance(f, models.DecimalField):
                        setattr(obj, f.name, Decimal(str(round(random.uniform(1, 200), 2))))
                    elif isinstance(f, models.BooleanField):
                        setattr(obj, f.name, True)
                    elif isinstance(f, models.DateTimeField):
                        setattr(obj, f.name, timezone.now())
                except Exception:
                    pass

            obj.save()
            created += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Creados {created} productos aleatorios."))
