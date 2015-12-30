# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
from django.conf import settings

AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Renaming model 'LoggedRequest'
        db.rename_table('security_loggedrequest', 'security_inputloggedrequest')
        if not db.dry_run:
            orm['contenttypes.contenttype'].objects.filter(
                app_label='security', model='loggedrequest').update(model='inputloggedrequest')

    def backwards(self, orm):
        # Renaming model 'InputLoggedRequest'
        db.rename_table('security_inputloggedrequest', 'security_loggedrequest')
        if not db.dry_run:
            orm['contenttypes.contenttype'].objects.filter(
                app_label='security', model='inputloggedrequest').update(model='loggedrequest')

    models = {
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'security.inputloggedrequest': {
            'Meta': {'object_name': 'InputLoggedRequest'},
            'error_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'headers': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.GenericIPAddressField', [], {'max_length': '39'}),
            'is_secure': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'method': ('django.db.models.fields.CharField', [], {'max_length': '7'}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'queries': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'request_body': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'request_timestamp': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'response_body': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'response_code': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'response_timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'status': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['users.User']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'})
        },
        AUTH_USER_MODEL.lower(): {
            'Meta': {'object_name': AUTH_USER_MODEL.rsplit('.', 1)[1]},
        }
    }

    complete_apps = ['security']