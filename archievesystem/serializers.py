from rest_framework import serializers
from .models import InternalEntity, InternalDepartment, ExternalEntity, ExternalDepartment, Document





class EntityTypeSerializer(serializers.Serializer):
    entity_type = serializers.ChoiceField(choices=[('internal', 'Internal'), ('external', 'External')])

class InternalEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = InternalEntity
        fields = ['id','name']

class InternalDepartmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = InternalDepartment
        fields = ['id','name','internal_entity']

class ExternalEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalEntity
        fields = ['id','name']

class ExternalDepartmentSerializer(serializers.ModelSerializer):
   
    class Meta:
        model = ExternalDepartment
        fields = ['id','name','external_entity']





class GetDocumentSerializer(serializers.ModelSerializer):
    internal_entity = InternalEntitySerializer()
    internal_department= InternalDepartmentSerializer()
    external_entity = ExternalEntitySerializer()
    external_department = ExternalDepartmentSerializer()
    uploaded_by = serializers.StringRelatedField()
    
    class Meta:
        model = Document
        fields = '__all__'



class DocumentSerializer(serializers.ModelSerializer):
    
    uploaded_by = serializers.HiddenField(default=serializers.CurrentUserDefault())
    file = serializers.FileField(required=False)  # ← كده الملف مش مطلوب دايمًا

    class Meta:
        model = Document
        fields = '__all__'

    def validate(self, data):
        entity_type = data.get('entity_type')
        internal_entity = data.get('internal_entity')
        internal_department = data.get('internal_department')
        external_entity = data.get('external_entity')
        external_department = data.get('external_department')

        if entity_type == 'internal':
            if not internal_entity or not internal_department:
                raise serializers.ValidationError("يجب تحديد الجهة والإدارة الداخلية.")
            if external_entity or external_department:
                raise serializers.ValidationError("لا يجب تحديد جهة أو إدارة خارجية مع كيان داخلي.")

            # ✅ التحقق إن الإدارة تنتمي للجهة
            if internal_department.internal_entity != internal_entity:
                raise serializers.ValidationError("الإدارة لا تنتمي إلى الجهة المحددة.")

        elif entity_type == 'external':
            if not external_entity or not external_department:
                raise serializers.ValidationError("يجب تحديد الجهة والإدارة الخارجية.")
            if internal_entity or internal_department:
                raise serializers.ValidationError("لا يجب تحديد جهة أو إدارة داخلية مع كيان خارجي.")

            # ✅ التحقق إن الإدارة الخارجية تنتمي للجهة الخارجية
            if external_department.external_entity != external_entity:
                raise serializers.ValidationError("الإدارة الخارجية لا تنتمي إلى الجهة الخارجية المحددة.")

        return data