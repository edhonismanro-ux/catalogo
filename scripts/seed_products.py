import random
from decimal import Decimal
from shop.models import Product

NAMES = [
    "Collar minimal", "Pulsera artesanal", "Aretes dorados", "Anillo ajustable",
    "Vela aromática", "Jabón natural", "Crema hidratante", "Perfume roll-on",
    "Taza personalizada", "Cuaderno premium", "Agenda 2026", "Porta celular",
    "Polo estampado", "Gorra urbana", "Bolso tote", "Billetera slim",
    "Chocolate artesanal", "Galletas caseras", "Mermelada natural", "Café premium",
]

DESCRIPTIONS = [
    "Producto hecho con mucho cariño. Ideal para regalo.",
    "Alta calidad, acabado profesional y duradero.",
    "Edición limitada. Stock sujeto a disponibilidad.",
    "Diseño moderno y elegante. Recomendado por clientes.",
    "Materiales seleccionados y presentación bonita.",
]

def run(count=24):
    created = 0
    for _ in range(count):
        name = random.choice(NAMES) + f" #{random.randint(10, 999)}"
        price = Decimal(str(random.choice([9.90, 12.50, 15.00, 19.90, 24.90, 29.90, 39.90, 49.90, 59.90])))
        stock = random.randint(0, 25)
        description = random.choice(DESCRIPTIONS)

        Product.objects.create(
            name=name,
            description=description,
            price=price,
            stock=stock,
            is_active=True,
        )
        created += 1

    print(f"✅ Listo: {created} productos creados.")
