from django.contrib.auth.views import LoginView
from django.http import HttpResponseForbidden
from django.shortcuts import render


class SmartLoginView(LoginView):
    template_name = 'login.html'

    def form_valid(self, form):
        user = form.get_user()
        login_type = self.request.POST.get('login_type', 'normal')
        if login_type == 'admin' and not (user.is_superuser or user.is_staff):
            form.add_error(None, '您没有管理员权限，请使用普通登录')
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return '/admin/'
        return '/workflow/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_tab'] = self.request.POST.get('login_type', 'normal')
        return context


def admin_guard(get_response):
    def middleware(request):
        if request.path.startswith('/admin/') and not request.path.startswith('/admin/login'):
            if request.user.is_authenticated and not (request.user.is_staff or request.user.is_superuser):
                return HttpResponseForbidden(
                    render(request, '403.html').content
                )
        return get_response(request)
    return middleware
