from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gyms', '0006_alter_gym_politica_visitantes'),
    ]

    operations = [
        migrations.AddField(
            model_name='gym',
            name='razon_social',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
