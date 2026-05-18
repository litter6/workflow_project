from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('pending/', views.my_pending, name='my_pending'),
    path('applied/', views.my_applied, name='my_applied'),
    path('handled/', views.my_handled, name='my_handled'),
    path('start/', views.start_process, name='start_process'),
    path('detail/<int:instance_id>/', views.instance_detail, name='instance_detail'),
    path('withdraw/<int:instance_id>/', views.withdraw, name='withdraw'),
    path('files/<int:instance_id>/', views.file_manager, name='file_manager'),
    path('notifications/', views.notifications, name='notifications'),
    path('projects/', views.project_list, name='project_list'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('quotations/', views.quotation_list, name='quotation_list'),
    path('quotations/create/<int:project_id>/', views.quotation_create, name='quotation_create'),
    path('quotations/<int:quotation_id>/', views.quotation_detail, name='quotation_detail'),
    path('prices/', views.price_list, name='price_list'),
    path('prices/save/', views.price_item_save, name='price_item_save'),
    path('prices/<int:pk>/delete/', views.price_item_delete, name='price_item_delete'),
    path('reports/', views.reports, name='reports'),
]
