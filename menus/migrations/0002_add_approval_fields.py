from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    # ถ้าไฟล์แรกของคุณชื่อ 0001_initial จริง ก็ไม่ต้องแก้บรรทัดนี้
    dependencies = [
        ('menus', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='menu',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[('PENDING','รออนุมัติ'),('APPROVED','อนุมัติแล้ว'),('REJECTED','ถูกปฏิเสธ')],
                default='PENDING',
            ),
        ),
        migrations.AddField(
            model_name='menu',
            name='approved_by',
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True, related_name='approved_menus'
            ),
        ),
        migrations.AddField(
            model_name='menu',
            name='approved_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]
