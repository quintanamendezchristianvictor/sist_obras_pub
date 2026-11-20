from django.db import migrations, models


def actualizar_provincia(apps, schema_editor):
    Obra = apps.get_model("obras", "Obra")
    Obra.objects.filter(provincia="Huanta").update(provincia="La Mar")


class Migration(migrations.Migration):

    dependencies = [
        ("obras", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(actualizar_provincia, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="obra",
            name="provincia",
            field=models.CharField(default="La Mar", max_length=100, verbose_name="Provincia"),
        ),
    ]
