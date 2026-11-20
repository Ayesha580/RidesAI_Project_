import os
import sys
from datetime import date, timedelta
from decimal import Decimal

# Setup Django environment
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from companies.models import Company, BusinessKnowledge
from operations.models import Doctor, Patient, Appointment
from accounts.models import StaffRole

User = get_user_model()


def seed():
    print("=== Seeding Shifa Medical Clinic Test Data ===")

    # 1. Company Creation & Activation
    company = Company.objects.filter(name__icontains="Shifa Medical").first()
    if not company:
        company = Company.objects.create(
            name="Shifa Medical Clinic",
            business_type="clinic",
            address="Jail Road, Civil Lines, Faisalabad",
            email="info@shifaclinic.pk",
            phone="03011223344",
            status="active",
            is_approved=True,
            subscription_status="active",
            is_manual_override=True,
        )
        print("Created new Shifa Medical Clinic company.")
    else:
        company.business_type = "clinic"
        company.status = "active"
        company.is_approved = True
        company.subscription_status = "active"
        company.is_manual_override = True
        company.save()
        print(f"Found and activated Shifa Medical Clinic (ID: {company.id}).")

    # 2. Staff Roles & Users
    # Role: Receptionist
    receptionist_role, _ = StaffRole.objects.get_or_create(
        company=company,
        name="Receptionist",
        defaults={
            "modules": ["orders", "appointments", "doctors", "patients", "pos"],
            "permissions": [
                "orders.view",
                "orders.create",
                "orders.update_status",
                "customers.view",
                "appointments.view",
                "appointments.manage",
                "doctors.view",
                "doctors.manage",
                "patients.view",
                "patients.manage",
                "agent.view",
            ],
            "is_active": True,
        }
    )
    receptionist_role.modules = ["orders", "appointments", "doctors", "patients", "pos"]
    receptionist_role.permissions = [
        "orders.view",
        "orders.create",
        "orders.update_status",
        "customers.view",
        "appointments.view",
        "appointments.manage",
        "doctors.view",
        "doctors.manage",
        "patients.view",
        "patients.manage",
        "agent.view",
    ]
    receptionist_role.save()

    # Owner: owner@shifaclinic.pk
    owner_user, o_created = User.objects.get_or_create(
        email="owner@shifaclinic.pk",
        defaults={
            "username": "owner@shifaclinic.pk",
            "company": company,
            "role": User.ROLE_OWNER,
            "email_verified": True,
        }
    )
    owner_user.company = company
    owner_user.role = User.ROLE_OWNER
    owner_user.email_verified = True
    owner_user.set_password("Password123!")
    owner_user.save()
    print(f"Owner Account: {owner_user.email} (Password: Password123!)")

    # Receptionist: reception@shifaclinic.pk
    reception_user, r_created = User.objects.get_or_create(
        email="reception@shifaclinic.pk",
        defaults={
            "username": "reception@shifaclinic.pk",
            "company": company,
            "role": User.ROLE_STAFF,
            "staff_role": receptionist_role,
            "email_verified": True,
        }
    )
    reception_user.company = company
    reception_user.role = User.ROLE_STAFF
    reception_user.staff_role = receptionist_role
    reception_user.email_verified = True
    reception_user.set_password("Password123!")
    reception_user.save()
    print(f"Staff (Receptionist): {reception_user.email} (Password: Password123!)")

    # 3. Doctors
    doctors_spec = [
        {
            "name": "Dr. Ayesha Tariq",
            "specialty": "General Physician",
            "qualification": "MBBS, FCPS (Medicine)",
            "consultation_fee": Decimal("1500.00"),
            "available_days": "Mon-Sat",
            "available_hours": "10:00 AM - 04:00 PM",
        },
        {
            "name": "Dr. Bilal Ahmed",
            "specialty": "Cardiologist",
            "qualification": "MBBS, MD (Cardiology), Dip. Interventional Cardiology",
            "consultation_fee": Decimal("2500.00"),
            "available_days": "Mon-Fri",
            "available_hours": "05:00 PM - 09:00 PM",
        },
        {
            "name": "Dr. Sana Malik",
            "specialty": "Dermatologist",
            "qualification": "MBBS, MCPS (Dermatology), Aesthetic Medicine",
            "consultation_fee": Decimal("2000.00"),
            "available_days": "Tue-Sat",
            "available_hours": "12:00 PM - 06:00 PM",
        },
    ]

    doctors_map = {}
    for spec in doctors_spec:
        doc, _ = Doctor.objects.get_or_create(
            company=company,
            name=spec["name"],
            defaults={
                "specialty": spec["specialty"],
                "qualification": spec["qualification"],
                "consultation_fee": spec["consultation_fee"],
                "available_days": spec["available_days"],
                "available_hours": spec["available_hours"],
                "is_active": True,
            }
        )
        doc.specialty = spec["specialty"]
        doc.qualification = spec["qualification"]
        doc.consultation_fee = spec["consultation_fee"]
        doc.available_days = spec["available_days"]
        doc.available_hours = spec["available_hours"]
        doc.is_active = True
        doc.save()
        doctors_map[doc.name] = doc
        print(f"Doctor: {doc.name} | {doc.specialty} | Fee: Rs. {doc.consultation_fee} | {doc.available_days} ({doc.available_hours})")

    # 4. Patients
    patients_spec = [
        {
            "name": "Kamran Akram",
            "phone": "03009876543",
            "age": 42,
            "gender": "Male",
            "notes": "Mild hypertension, seasonal allergies",
        },
        {
            "name": "Zainab Bibi",
            "phone": "03217654321",
            "age": 29,
            "gender": "Female",
            "notes": "Skin consultation, routine checkup",
        },
    ]

    patients_map = {}
    for ps in patients_spec:
        pat, _ = Patient.objects.get_or_create(
            company=company,
            phone=ps["phone"],
            defaults={
                "name": ps["name"],
                "age": ps["age"],
                "gender": ps["gender"],
                "notes": ps["notes"],
            }
        )
        pat.name = ps["name"]
        pat.age = ps["age"]
        pat.gender = ps["gender"]
        pat.notes = ps["notes"]
        pat.save()
        patients_map[pat.phone] = pat
        print(f"Patient: {pat.name} | 📞 {pat.phone} | Age: {pat.age} | Notes: {pat.notes}")

    # 5. Appointments
    today = date.today()
    apts_spec = [
        {
            "patient": patients_map["03009876543"],
            "doctor": doctors_map["Dr. Bilal Ahmed"],
            "date": today + timedelta(days=1),
            "time": "06:00 PM",
            "reason": "Routine cardiac checkup and blood pressure monitoring",
            "status": Appointment.STATUS_PENDING,
            "source": "whatsapp_ai",
        },
        {
            "patient": patients_map["03217654321"],
            "doctor": doctors_map["Dr. Sana Malik"],
            "date": today + timedelta(days=2),
            "time": "02:00 PM",
            "reason": "Skin rash and allergy consultation",
            "status": Appointment.STATUS_CONFIRMED,
            "source": "dashboard",
        },
    ]

    for a in apts_spec:
        pat = a["patient"]
        doc = a["doctor"]
        apt, _ = Appointment.objects.get_or_create(
            company=company,
            patient=pat,
            doctor=doc,
            appointment_date=a["date"],
            defaults={
                "patient_name": pat.name,
                "patient_phone": pat.phone,
                "appointment_time": a["time"],
                "reason": a["reason"],
                "status": a["status"],
                "source": a["source"],
            }
        )
        apt.patient_name = pat.name
        apt.patient_phone = pat.phone
        apt.appointment_time = a["time"]
        apt.reason = a["reason"]
        apt.status = a["status"]
        apt.source = a["source"]
        apt.save()
        print(f"Appointment: {apt.appointment_number} | {apt.patient_name} with {doc.name} | Date: {apt.appointment_date} {apt.appointment_time} | Status: {apt.status} ({apt.source})")

    # 6. Knowledge Base FAQs
    faqs = [
        {
            "title": "Clinic Timings & Consultation Hours",
            "content": "Shifa Medical Clinic is open Monday to Saturday from 10:00 AM to 09:00 PM. Specialist doctors consult at their designated schedules.",
            "entry_type": "faq",
        },
        {
            "title": "Emergency Policy",
            "content": "For life-threatening emergencies, please proceed immediately to the nearest hospital emergency department or call 1122. We provide outpatient specialist consultations.",
            "entry_type": "policy",
        },
    ]

    for faq in faqs:
        kb, _ = BusinessKnowledge.objects.get_or_create(
            company=company,
            title=faq["title"],
            defaults={
                "content": faq["content"],
                "entry_type": faq["entry_type"],
                "is_approved": True,
                "is_active": True,
                "source": "business",
            }
        )
        kb.content = faq["content"]
        kb.entry_type = faq["entry_type"]
        kb.is_approved = True
        kb.is_active = True
        kb.source = "business"
        kb.save()
        print(f"Knowledge FAQ: '{kb.title}' -> '{kb.content}'")

    print("\n=== Seeding Finished Successfully! ===")


if __name__ == "__main__":
    seed()
