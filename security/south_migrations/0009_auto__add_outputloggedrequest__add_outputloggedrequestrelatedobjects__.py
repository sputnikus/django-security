# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'OutputLoggedRequest'
        db.create_table(u'security_outputloggedrequest', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('host', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('request_timestamp', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('method', self.gf('django.db.models.fields.CharField')(max_length=7)),
            ('path', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('queries', self.gf('json_field.fields.JSONField')(default=u'null', null=True, blank=True)),
            ('request_headers', self.gf('json_field.fields.JSONField')(default=u'null', null=True, blank=True)),
            ('request_body', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('is_secure', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('response_timestamp', self.gf('django.db.models.fields.DateTimeField')()),
            ('response_code', self.gf('django.db.models.fields.PositiveSmallIntegerField')()),
            ('response_headers', self.gf('json_field.fields.JSONField')(default=u'null', null=True, blank=True)),
            ('status', self.gf('django.db.models.fields.PositiveSmallIntegerField')()),
            ('type', self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1)),
            ('response_body', self.gf('django.db.models.fields.TextField')(blank=True)),
            ('error_description', self.gf('django.db.models.fields.TextField')(null=True, blank=True)),
        ))
        db.send_create_signal(u'security', ['OutputLoggedRequest'])

        # Adding model 'OutputLoggedRequestRelatedObjects'
        db.create_table(u'security_outputloggedrequestrelatedobjects', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('output_logged_request', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['security.OutputLoggedRequest'])),
            ('content_type', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['contenttypes.ContentType'])),
            ('object_id', self.gf('django.db.models.fields.PositiveIntegerField')()),
        ))
        db.send_create_signal(u'security', ['OutputLoggedRequestRelatedObjects'])

        # Deleting field 'InputLoggedRequest.headers'
        db.delete_column(u'security_inputloggedrequest', 'headers')

        # Adding field 'InputLoggedRequest.host'
        db.add_column(u'security_inputloggedrequest', 'host',
                      self.gf('django.db.models.fields.CharField')(default='empty', max_length=255),
                      keep_default=False)

        # Adding field 'InputLoggedRequest.request_headers'
        db.add_column(u'security_inputloggedrequest', 'request_headers',
                      self.gf('json_field.fields.JSONField')(default=u'null', null=True, blank=True),
                      keep_default=False)

        # Adding field 'InputLoggedRequest.response_headers'
        db.add_column(u'security_inputloggedrequest', 'response_headers',
                      self.gf('json_field.fields.JSONField')(default=u'null', null=True, blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting model 'OutputLoggedRequest'
        db.delete_table(u'security_outputloggedrequest')

        # Deleting model 'OutputLoggedRequestRelatedObjects'
        db.delete_table(u'security_outputloggedrequestrelatedobjects')

        # Adding field 'InputLoggedRequest.headers'
        db.add_column(u'security_inputloggedrequest', 'headers',
                      self.gf('json_field.fields.JSONField')(default=u'null', null=True, blank=True),
                      keep_default=False)

        # Deleting field 'InputLoggedRequest.host'
        db.delete_column(u'security_inputloggedrequest', 'host')

        # Deleting field 'InputLoggedRequest.request_headers'
        db.delete_column(u'security_inputloggedrequest', 'request_headers')

        # Deleting field 'InputLoggedRequest.response_headers'
        db.delete_column(u'security_inputloggedrequest', 'response_headers')


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
            'response_body': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'response_code': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'response_headers': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'response_timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'status': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'}),
            'user': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['users.User']", 'null': 'True', 'on_delete': 'models.SET_NULL', 'blank': 'True'})
        },
        u'security.outputloggedrequest': {
            'Meta': {'object_name': 'OutputLoggedRequest'},
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
            'response_body': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'response_code': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'response_headers': ('json_field.fields.JSONField', [], {'default': "u'null'", 'null': 'True', 'blank': 'True'}),
            'response_timestamp': ('django.db.models.fields.DateTimeField', [], {}),
            'status': ('django.db.models.fields.PositiveSmallIntegerField', [], {}),
            'type': ('django.db.models.fields.PositiveSmallIntegerField', [], {'default': '1'})
        },
        u'security.outputloggedrequestrelatedobjects': {
            'Meta': {'object_name': 'OutputLoggedRequestRelatedObjects'},
            'content_type': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['contenttypes.ContentType']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'object_id': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'output_logged_request': ('django.db.models.fields.related.ForeignKey', [], {'to': u"orm['security.OutputLoggedRequest']"})
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