from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import MerchantViewSet, PayoutViewSet

router = DefaultRouter()
router.register(r'merchants', MerchantViewSet, basename='merchant')
router.register(r'payouts', PayoutViewSet, basename='payout')

urlpatterns = [
    path('', include(router.urls)),
]
