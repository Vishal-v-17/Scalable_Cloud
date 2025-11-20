from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_redirect, name='login'),
    path('callback/', views.callback, name='callback'),
    path('logout/', views.logout_view, name='logout'),
    path('rooms/<uuid:pk>/', views.room_detail, name='room_detail'),
    path('rooms/<uuid:pk>/book/', views.book_room, name='book_room'),
    path('booking/<uuid:pk>/', views.booking_detail, name='booking_detail'),
    path('booking/<uuid:booking_id>/pay/', views.pay_booking, name='pay_booking'),
    path('rooms/', views.list_room_types, name='list_room_types'),
    path('rooms/add', views.add_room_type, name='add_room_type'),
    path('room-types/<uuid:room_type_id>/edit/', views.add_room_type, name='edit_room_type'),
]
