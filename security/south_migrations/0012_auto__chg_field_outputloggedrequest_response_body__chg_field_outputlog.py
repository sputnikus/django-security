# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'OutputLoggedRequest.response_body'
        db.alter_column(u'security_outputloggedrequest', 'response_body', self.gf('django.db.models.fields.TextField')(null=True))

        # Changing field 'OutputLoggedRequest.response_code'
        db.alter_column(u'security_outputloggedrequest', 'response_code', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True))

        # Changing field 'OutputLoggedRequest.response_timestamp'
        db.alter_column(u'security_outputloggedrequest', 'response_timestamp', self.gf('django.db.models.fields.DateTimeField')(null=True))

        # Changing field 'InputLoggedRequest.response_body'
        db.alter_column(u'security_inputloggedrequest', 'response_body', self.gf('django.db.models.fields.TextField')(null=True))

        # Changing field 'InputLoggedRequest.response_code'
        db.alter_column(u'security_inputloggedrequest', 'response_code', self.gf('django.db.models.fields.PositiveSmallIntegerField')(null=True))

        # Changing field 'InputLoggedRequest.response_timestamp'
        db.alter_column(u'security_inputloggedrequest', 'response_timestamp', self.gf('django.db.models.fields.DateTimeField')(null=True))

    def backwards(self, orm):

        # Changing field 'OutputLoggedRequest.response_body'
        db.alter_column(u'security_outputloggedrequest', 'response_body', self.gf('django.db.models.fields.TextField')(default=''))

        # User chose to not deal with backwards NULL issues for 'OutputLoggedRequest.response_code'
        raise RuntimeError("Cannot reverse this migration. 'OutputLoggedRequest.response_code' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration
        # Changing field 'OutputLoggedRequest.response_code'
        db.alter_column(u'security_outputloggedrequest', 'response_code', self.gf('django.db.models.fields.PositiveSmallIntegerField')())

        # User chose to not deal with backwards NULL issues for 'OutputLoggedRequest.response_timestamp'
        raise RuntimeError("Cannot reverse this migration. 'OutputLoggedRequest.response_timestamp' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration
        # Changing field 'OutputLoggedRequest.response_timestamp'
        db.alter_column(u'security_outputloggedrequest', 'response_timestamp', self.gf('django.db.models.fields.DateTimeField')())

        # Changing field 'InputLoggedRequest.response_body'
        db.alter_column(u'security_inputloggedrequest', 'response_body', self.gf('django.db.models.fields.TextField')(default=''))

        # User chose to not deal with backwards NULL issues for 'InputLoggedRequest.response_code'
        raise RuntimeError("Cannot reverse this migration. 'InputLoggedRequest.response_code' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration
        # Changing field 'InputLoggedRequest.response_code'
        db.alter_column(u'security_inputloggedrequest', 'response_code', self.gf('django.db.models.fields.PositiveSmallIntegerField')())

        # User chose to not deal with backwards NULL issues for 'InputLoggedRequest.response_timestamp'
        raise RuntimeError("Cannot reverse this migration. 'InputLoggedRequest.response_timestamp' and its values cannot be restored.")
        
        # The following code is provided here to aid in writing a correct migration
        # Changing field 'InputLoggedRequest.response_timestamp'
        db.alter_column(u'security_inputloggedrequest', 'response_timestamp', self.gf('django.db.models.fields.DateTimeField')())

    models = {
        u'contenttypes.contenttype': {
            'Meta': {'ordering': "('name',)", 'unique_together': "(('app_label', 'model'),)", 'object_name': 'ContentType', 'db_table': "'django_content_type'"},
            'app_label': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '100'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        u'security.inputloggedrequest': {
            'Meta': {'ordering': "(u'-request_timestamp',)", 'object_name': 'InputLoggedRequest'},
            'error_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'host': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'ip': ('django.db.models.fields.GenericIPAddressField', [], {'max_length': '39'}),
            'is_secure': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'method': ('django.db.models.fields.CharField', [], {'max_length': '7'}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'queries': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'request_body': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'request_headers': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'request_timestamp': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'response_body': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'response_code': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'response_headers': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'response_timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['users.User']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'})
        },
        u'security.outputloggedrequest': {
            'Meta': {'ordering': "(u'-request_timestamp',)", 'object_name': 'OutputLoggedRequest'},
            'error_description': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'host': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_secure': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'method': ('django.db.models.fields.CharField', [], {'max_length': '7'}),
            'path': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'queries': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'request_body': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'request_headers': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'request_timestamp': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'response_body': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'response_code': ('django.db.models.fields.PositiveSmallIntegerField', [], {'null': 'True', 'blank': 'True'}),
            'response_headers': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'response_timestamp': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'slug': ('django.db.models.fields.SlugField', [], {'max_length': '50', 'null': 'True', 'blank': 'True'}),
            'status': ('django.db.models.fields.PositiveSmallIntegerField', [], {})
        },
        u'security.outputloggedrequestrelatedobjects': {
            'Meta': {'object_name': 'OutputLoggedRequestRelatedObjects'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'output_logged_request': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "u'related_objects'", 'to': u"orm['security.OutputLoggedRequest']"})
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