# -*- coding: utf-8 -*-
import os
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import DataMigration
from django.db import models

from django_image_tools.models import md5Checksum

class Migration(DataMigration):

    def forwards(self, orm):
        "Map profile picture image fields into django-image-tools Image model."
        # Note: Don't use "from appname.models import ModelName".
        # Use orm.ModelName to refer to models in this application,
        # and orm['appname.ModelName'] for models in other applications.
        Image = orm['django_image_tools.Image']

        for profile_pic in orm.ProfilePicture.objects.all():
            # create a new Image object and link to profile pic,
            # using profile picture fields for image fields
            new_image = Image(title=profile_pic.title,
                caption=profile_pic.title,
                alt_text=profile_pic.title,
                credit=profile_pic.permissions,
                image=profile_pic.img.path,
                checksum=md5Checksum(profile_pic.img.path))

            # Image seems to require filename, but not set it
            # NOTE: image migration is not fully working, but may at least save
            # some manual effort in converting from old db setup to new
            basename, ext = os.path.splitext(os.path.basename(profile_pic.img.path))
            new_image.filename = basename

            # save the image and associated it with the profile pic record
            new_image.save()
            # explicitly set the id, since the schema migration sets it to 01
            profile_pic.image_id = new_image.id
            profile_pic.save()

    def backwards(self, orm):
        "Map django-image-tools Image model fields to profile picture Image."

        for profile_pic in orm.ProfilePicture.objects.all():
            # set profile pic from image title
            profile_pic.title = profile_pic.image.title
            # set local profile pic image from image
            profile_pic.img = profile_pic.image.image
            # delete the Image object created on the forward migration
            profile_pic.image.delete()
            profile_pic.save()

    models = {
        u'django_image_tools.image': {
            'Meta': {'object_name': 'Image'},
            'alt_text': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'caption': ('django.db.models.fields.TextField', [], {}),
            'checksum': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'credit': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'filename': ('django.db.models.fields.SlugField', [], {'max_length': '50'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.files.ImageField', [], {'max_length': '100'}),
            'subject_position_horizontal': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '2'}),
            'subject_position_vertical': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '2'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'was_upscaled': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        u'people.profilepicture': {
            'Meta': {'object_name': 'ProfilePicture'},
            'collection_uri': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'creator': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'date': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'image': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'profilepicture_set'", 'to': u"orm['django_image_tools.Image']"}),
            'img': ('django.db.models.fields.files.ImageField', [], {'max_length': '100'}),
            'permissions': ('django.db.models.fields.TextField', [], {}),
            'person_uri': ('django.db.models.fields.URLField', [], {'unique': 'True', 'max_length': '200'}),
            'publisher': ('django.db.models.fields.CharField', [], {'max_length': '255', 'blank': 'True'}),
            'publisher_url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'thumbnail': ('django.db.models.fields.files.ImageField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['people']
    symmetrical = True