# Generated by Django 2.1.1 on 2019-01-29 08:04

from django.db import migrations, models
import tally_ho.apps.tally.models.ballot
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('tally', '0014_resultform_previous_form_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='ballot',
            name='document',
            field=models.FileField(blank=True, default=None, null=True, upload_to=tally_ho.apps.tally.models.ballot.ballot_document_directory_path),
        ),
        migrations.AddField(
            model_name='ballot',
            name='unique_uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name='resultform',
            name='reject_reason',
            field=models.TextField(blank=True, null=True),
        ),
    ]
