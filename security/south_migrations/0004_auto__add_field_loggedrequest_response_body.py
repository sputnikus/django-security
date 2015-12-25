# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models
from django.conf import settings

AUTH_USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'LoggedRequest.response_body'
        db.add_column(u'security_loggedrequest', 'response_body',
                      self.gf('django.db.models.fields.TextField')(default='', blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'LoggedRequest.response_body'
        db.delete_column(u'security_loggedrequest', 'response_body')


    models = {
        u'security.loggedrequest': {
            'Meta': {'ordering': "(u'-request_timestamp',)", 'object_name': 'LoggedRequest'},
            'error_description': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True', 'blank': 'True'}),
            'headers': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
            'is_secure': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'method': ('django.db.models.fields.CharField', [], {'max_length': '7'}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'queries': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'request_body': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'request_timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'response_body': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'response_code': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'response_timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'status': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['%s']" % AUTH_USER_MODEL, 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'})
        },
        AUTH_USER_MODEL.lower(): {
            'Meta': {'object_name': AUTH_USER_MODEL.rsplit('.', 1)[1]},
        }
    }

    complete_apps = ['security']