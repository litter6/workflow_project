from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from accounts.views import SmartLoginView

admin.site.site_header = '企业工作流管理系统'
admin.site.site_title = '工作流系统'
admin.site.index_title = '系统管理后台'


def smart_redirect(request):
    if not request.user.is_authenticated:
        return redirect('/login/')
    if request.user.is_superuser or request.user.is_staff:
        return redirect('/admin/')
    return redirect('/workflow/')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('workflow/', include('workflows.urls')),
    path('login/', SmartLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/login/'), name='logout'),
    path('', smart_redirect),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)