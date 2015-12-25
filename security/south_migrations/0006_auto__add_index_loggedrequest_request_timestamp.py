# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding index on 'LoggedRequest', fields ['request_timestamp']
        db.create_index(u'security_loggedrequest', ['request_timestamp'])


    def backwards(self, orm):
        # Removing index on 'LoggedRequest', fields ['request_timestamp']
        db.delete_index(u'security_loggedrequest', ['request_timestamp'])


    models = {
        u'security.loggedrequest': {
            'Meta': {'ordering': "(u'-request_timestamp',)", 'object_name': 'LoggedRequest'},
            'error_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'headers': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.IPAddressField', [], {'max_length': '15'}),
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
        u'users.user': {
            'Meta': {'unique_together': "((u'email', u'domain'),)", 'object_name': 'User'},
            'changed_at': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'}),
            'created_at': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'domain': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'is_verified': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'last_login': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now'}),
            'password': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'username': ('django.db.models.fields.CharField', [], {'max_length': '80', 'unique': 'True', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['security']