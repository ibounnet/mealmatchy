# mealmatchy_backend/urls.py
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='home', permanent=False)),  # หรือ menu_list ถ้าต้องการ
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('menus/', include(('menus.urls', 'menus'), namespace='menus')),

    
    path("plan/", include(("plan.urls", "plan"), namespace="plan")),
    path("budget/", include(("budgets.urls", "budgets"), namespace="budgets")),
    path('', include(('budgets.urls', 'budgets'), namespace='budgets')),
    
    path('recipes/', include('recipes.urls')),
    path('restaurants/', include(('restaurants.urls', 'restaurants'), namespace='restaurants')),


    path('register/', RedirectView.as_view(pattern_name='register', permanent=False)),
    path('login/',    RedirectView.as_view(pattern_name='login', permanent=False)),
    path('logout/', RedirectView.as_view(pattern_name='logout', permanent=False)),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
