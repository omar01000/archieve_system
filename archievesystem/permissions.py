from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsDocumentAccessible(BasePermission):
    """
    - SuperAdmin / Admin: صلاحيات كاملة
    - User: يقدر يشوف كل الملفات + يرفع ملفات
           لكن ما يقدرش يعدل أو يمسح أي حاجة
    """

    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            return False

        # السوبر أدمن والأدمن يقدروا يعملوا أي حاجة
        if user.is_superuser or user.groups.filter(name='Admin').exists():
            return True

        # المستخدم العادي:
        if request.method in SAFE_METHODS or request.method == 'POST':
            return True

        # يترفض أي تعديل أو حذف
        return False

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.is_superuser or user.groups.filter(name='Admin').exists():
            return True

        # المستخدم العادي يقدر يشوف بس أي مستند (مش شرط يكون بتاعه)
        if request.method in SAFE_METHODS:
            return True

        # ما يقدرش يعدل أو يمسح
        return False




    
    
class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        if request.method in SAFE_METHODS:
            return True

        return user.is_superuser or user.groups.filter(name='Admin').exists()    
