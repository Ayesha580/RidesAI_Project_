from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsCompanyPaymentActive
from accounts.models import User
from .models import BusinessLocation, BusinessHours, ServiceArea, BusinessKnowledge

class OwnerOnly(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and getattr(request.user, 'role', None) == User.ROLE_OWNER and bool(getattr(request.user, 'company_id', None))

class TenantOwnerViewSet(viewsets.ModelViewSet):
    permission_classes = [OwnerOnly, IsCompanyPaymentActive]
    def get_queryset(self): return self.queryset.filter(company=self.request.user.company)
    def perform_create(self, serializer): serializer.save(company=self.request.user.company)

class LocationSerializer(serializers.ModelSerializer):
    class Meta: model=BusinessLocation; fields=['id','name','address','city','country','phone','latitude','longitude','is_primary','is_active','created_at']; read_only_fields=['id','created_at']
class LocationViewSet(TenantOwnerViewSet): queryset=BusinessLocation.objects.all(); serializer_class=LocationSerializer
class HoursSerializer(serializers.ModelSerializer):
    class Meta: model=BusinessHours; fields=['id','location','day_of_week','opens_at','closes_at','is_closed']; read_only_fields=['id']
    def validate_location(self, value):
        if value and value.company_id != self.context['request'].user.company_id: raise serializers.ValidationError('Location belongs to another business.')
        return value
class HoursViewSet(TenantOwnerViewSet): queryset=BusinessHours.objects.all(); serializer_class=HoursSerializer
class ServiceAreaSerializer(serializers.ModelSerializer):
    class Meta: model=ServiceArea; fields=['id','name','area_type','city','country','center_latitude','center_longitude','radius_km','delivery_fee','is_active']; read_only_fields=['id']
    def validate(self, data):
        current = self.instance
        area_type = data.get('area_type', getattr(current, 'area_type', 'city'))
        city = data.get('city', getattr(current, 'city', ''))
        country = data.get('country', getattr(current, 'country', ''))
        lat = data.get('center_latitude', getattr(current, 'center_latitude', None))
        lon = data.get('center_longitude', getattr(current, 'center_longitude', None))
        radius = data.get('radius_km', getattr(current, 'radius_km', None))
        if area_type == 'radius' and (lat is None or lon is None or not radius): raise serializers.ValidationError('Radius areas require centre coordinates and radius_km.')
        if area_type == 'city' and not city: raise serializers.ValidationError('City is required for a city area.')
        if area_type == 'country' and not country: raise serializers.ValidationError('Country is required for a country area.')
        return data
class ServiceAreaViewSet(TenantOwnerViewSet): queryset=ServiceArea.objects.all(); serializer_class=ServiceAreaSerializer
class KnowledgeSerializer(serializers.ModelSerializer):
    class Meta: model=BusinessKnowledge; fields=['id','entry_type','title','content','is_approved','is_active','source','created_at','updated_at']; read_only_fields=['id','source','created_at','updated_at']
    def validate(self, data):
        request=self.context['request']
        if request.method in ('POST','PUT','PATCH') and data.get('source') == 'suggested' and 'is_approved' in data and data['is_approved'] and request.user.role != User.ROLE_OWNER: raise serializers.ValidationError('Only the business owner may approve suggested knowledge.')
        return data
class KnowledgeViewSet(TenantOwnerViewSet):
    queryset=BusinessKnowledge.objects.all()
    serializer_class=KnowledgeSerializer

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        entry=self.get_object(); entry.is_approved=True; entry.save(update_fields=['is_approved','updated_at']); return Response({'id':entry.id,'is_approved':True})

class DeliveryEligibilityAPIView(APIView):
    permission_classes=[IsAuthenticated, IsCompanyPaymentActive]
    def post(self, request):
        from math import radians, sin, cos, asin, sqrt
        company=request.user.company
        city=str(request.data.get('city','')).strip().casefold(); country=str(request.data.get('country','')).strip().casefold()
        lat=request.data.get('latitude'); lon=request.data.get('longitude')
        areas=company.service_areas.filter(is_active=True)
        matched=None
        for area in areas:
            ok=False
            if area.area_type=='city': ok=bool(city and city==area.city.casefold() and (not area.country or country==area.country.casefold()))
            elif area.area_type=='country': ok=bool(country and country==area.country.casefold())
            elif area.area_type=='radius' and lat is not None and lon is not None:
                try:
                    dlat=radians(float(lat)-float(area.center_latitude)); dlon=radians(float(lon)-float(area.center_longitude))
                    a=sin(dlat/2)**2+cos(radians(float(area.center_latitude)))*cos(radians(float(lat)))*sin(dlon/2)**2
                    km=6371*2*asin(sqrt(a)); ok=km<=float(area.radius_km)
                except (TypeError,ValueError): ok=False
            if ok: matched=area; break
        return Response({'eligible':bool(matched),'service_area':matched.name if matched else None,'delivery_fee':str(matched.delivery_fee) if matched else None,'message':'Delivery is available in this area.' if matched else 'Delivery is not available at this location.'})
