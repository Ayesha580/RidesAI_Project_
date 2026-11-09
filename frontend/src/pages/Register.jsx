import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { authApi } from "../api/authApi";
import { errorText } from "../api/axiosClient";
import Footer from "../components/Footer";
import Navbar from "../components/Navbar";
import "../styles/landing.css";
import "../styles/auth.css";

const BUSINESS_TYPES = [
  "Restaurant",
  "Pharmacy",
  "Grocery / General Store",
  "Clinic",
  "Retail Shop",
  "Other",
];

const initial = {
  first_name: "",
  username: "",
  email: "",
  phone: "",
  password: "",
  cnic: "",
  business_name: "",
  business_type: "Restaurant",
  custom_type: "",
  business_address: "",
  is_registered: false,
  registration_number: "",
};

function FileField({ label, name, accept, file, onChange, error, required = true }) {
  return (
    <div className="au-field">
      <label htmlFor={name}>{label}{required ? " *" : ""}</label>
      <label className={`au-file ${file ? "has-file" : ""} ${error ? "file-error" : ""}`} htmlFor={name}>
        <span className="au-file-icon">{file ? "✓" : "↑"}</span>
        <span className="au-file-text">{file ? file.name : "Choose file"}</span>
      </label>
      <input
        className="au-file-input"
        id={name}
        type="file"
        name={name}
        accept={accept}
        onChange={onChange}
        required={required}
      />
      {error && <small className="au-field-error">{error}</small>}
    </div>
  );
}

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm] = useState(initial);
  const [files, setFiles] = useState({});
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [registered, setRegistered] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState("");
  const [verificationSent, setVerificationSent] = useState(true);

  const change = (e) => {
    const { name, value, type, checked } = e.target;
    setForm({ ...form, [name]: type === "checkbox" ? checked : value });
    setFieldErrors((prev) => ({ ...prev, [name]: "" }));
    setError("");
  };

  const pickFile = (e) => {
    const { name, files: selectedFiles } = e.target;
    setFiles((prev) => ({ ...prev, [name]: selectedFiles[0] }));
    setFieldErrors((prev) => ({ ...prev, [name]: "" }));
    setError("");
  };

  const submit = async (e) => {
    e.preventDefault();
    if (registered || busy) return;

    setError("");
    setFieldErrors({});

    const errors = {};
    ["cnic_front", "cnic_back", "passport_size_photo"].forEach((name) => {
      if (!files[name]) errors[name] = "This document is required.";
    });

    const businessType = form.business_type === "Other" ? form.custom_type.trim() : form.business_type;
    if (!businessType) errors.custom_type = "Please enter your business type.";

    if (form.is_registered && !form.registration_number.trim()) {
      errors.registration_number = "Registration number is required.";
    }

    if (Object.keys(errors).length) {
      setFieldErrors(errors);
      return;
    }

    const { custom_type, ...rest } = form;
    const fd = new FormData();
    Object.entries({ ...rest, business_type: businessType }).forEach(([key, value]) => {
      fd.append(key, String(value));
    });
    Object.entries(files).forEach(([key, value]) => {
      if (value) fd.append(key, value);
    });

    setBusy(true);
    try {
      const { data } = await authApi.register(fd);
      const email = data.email || form.email;
      setVerificationEmail(email);
      setVerificationSent(data.verification_email_sent !== false);
      setRegistered(true);
      navigate(`/verify-email?email=${encodeURIComponent(email)}`);
    } catch (err) {
      const responseData = err?.response?.data;
      const backendErrors = {};
      const knownFields = [
        "first_name", "username", "email", "phone", "password", "cnic",
        "business_name", "business_type", "business_address",
        "registration_number", "business_registration_document",
        "cnic_front", "cnic_back", "passport_size_photo",
      ];

      if (responseData && typeof responseData === "object") {
        knownFields.forEach((key) => {
          if (responseData[key]) {
            const value = responseData[key];
            backendErrors[key] = Array.isArray(value) ? value.join(" ") : String(value);
          }
        });

        if (responseData.custom_type) {
          backendErrors.custom_type = Array.isArray(responseData.custom_type)
            ? responseData.custom_type.join(" ")
            : String(responseData.custom_type);
        }
      }

      if (Object.keys(backendErrors).length) {
        setFieldErrors(backendErrors);
        const otherErrors = Object.entries(responseData)
          .filter(([key]) => !knownFields.includes(key) && key !== "custom_type")
          .map(([, value]) => Array.isArray(value) ? value.join(" ") : String(value));
        if (otherErrors.length) setError(otherErrors.join(" "));
      } else {
        setError(errorText(err));
      }
    } finally {
      setBusy(false);
    }
  };

  const input = (label, name, extra = {}) => (
    <div className="au-field">
      <label htmlFor={name}>{label}{extra.required ? " *" : ""}</label>
      <input
        id={name}
        name={name}
        value={form[name]}
        onChange={change}
        aria-invalid={!!fieldErrors[name]}
        {...extra}
      />
      {fieldErrors[name] && <small className="au-field-error">{fieldErrors[name]}</small>}
    </div>
  );

  return (
    <div className="lp">
      <Navbar />
      <main className="au-main au-register-main">
        <div className="au-register-layout">
          <section className="au-register-heading">
            <span className="au-eyebrow">GET STARTED WITH RIDES AI</span>
            <h1>Set up your business workspace.</h1>
            <p>Bring your business operations, customers and AI assistant together in one place.</p>

            <div className="au-vector au-vector-register">
              <svg viewBox="0 0 420 230" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="95" y="25" width="230" height="180" rx="14" fill="#fff" stroke="#efdcef" strokeWidth="2"/>
                <rect x="120" y="48" width="180" height="30" rx="7" fill="#fff1ff"/>
                <circle cx="140" cy="63" r="7" fill="#ff77ff" opacity=".3"/>
                <path d="M137 63L140 66L145 60" stroke="#d94bd9" strokeWidth="2" strokeLinecap="round"/>
                <rect x="155" y="59" width="110" height="7" rx="3.5" fill="#e6cce6"/>
                <rect x="120" y="94" width="180" height="27" rx="6" fill="#faf6fb"/>
                <circle cx="137" cy="107" r="5" fill="#dca0ed"/>
                <rect x="153" y="103" width="90" height="7" rx="3.5" fill="#e6dce9"/>
                <rect x="120" y="132" width="180" height="27" rx="6" fill="#faf6fb"/>
                <circle cx="137" cy="145" r="5" fill="#ff77ff"/>
                <rect x="153" y="141" width="110" height="7" rx="3.5" fill="#e6dce9"/>
                <rect x="120" y="170" width="180" height="20" rx="6" fill="#ff77ff"/>
                <path d="M203 180H217" stroke="#fff" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="75" cy="65" r="23" fill="#fff0ff"/>
                <path d="M75 52L79 61L89 65L79 69L75 79L71 69L61 65L71 61L75 52Z" fill="#e56be5"/>
                <circle cx="350" cy="145" r="28" fill="#f8edff"/>
                <path d="M338 145L347 154L363 136" stroke="#b66bd1" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="335" cy="40" r="5" fill="#ff77ff"/>
                <circle cx="70" cy="175" r="5" fill="#dca0ed"/>
              </svg>
            </div>

            <div className="au-steps">
              <div className="au-step">
                <span>01</span>
                <div><strong>Business registration</strong><small>Provide your details and documents</small></div>
              </div>
              <div className="au-step">
                <span>02</span>
                <div><strong>Email verification</strong><small>Confirm your email address</small></div>
              </div>
              <div className="au-step">
                <span>03</span>
                <div><strong>Choose your plan</strong><small>Select a subscription and complete checkout</small></div>
              </div>
            </div>
          </section>

          <form className="au-card au-register-card" onSubmit={submit}>
            <div className="au-card-head">
              <span className="au-card-label">CREATE YOUR ACCOUNT</span>
              <h2>Business registration</h2>
              <p>Complete the details below to create your business account.</p>
            </div>

            {error && <div className="au-alert" role="alert">{error}</div>}

            {registered && (
              <div className="au-alert au-success" role="status">
                <strong>{verificationSent ? "Check your inbox" : "Email delivery needs attention"}</strong>
                <p>
                  {verificationSent
                    ? `We sent a six-digit verification code to ${verificationEmail}.`
                    : `Your account was created for ${verificationEmail}, but the verification email could not be delivered. Please use the resend option on the verification page.`}
                </p>
              </div>
            )}

            {!registered && (
              <>
                <fieldset className="au-section">
                  <div className="au-grid">
                    {input("Full name", "first_name", { required: true, placeholder: "Your full name" })}
                    {input("Username", "username", { required: true, autoComplete: "username", placeholder: "Choose a username" })}
                    {input("Email address", "email", { type: "email", required: true, placeholder: "name@example.com" })}
                    {input("Phone number", "phone", { required: true, placeholder: "03XXXXXXXXX" })}
                    {input("Password", "password", { type: "password", minLength: 8, required: true, autoComplete: "new-password", placeholder: "Minimum 8 characters" })}
                    {input("CNIC", "cnic", { required: true, placeholder: "12345-1234567-1" })}
                  </div>
                </fieldset>

                <fieldset className="au-section">
                  <legend>Business information</legend>
                  <div className="au-grid">
                    {input("Business name", "business_name", { required: true, placeholder: "Enter business name" })}
                    <div className="au-field">
                      <label htmlFor="business_type">Business type *</label>
                      <select
                        id="business_type"
                        name="business_type"
                        value={form.business_type}
                        onChange={change}
                        aria-invalid={!!fieldErrors.business_type}
                      >
                        {BUSINESS_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
                      </select>
                      {fieldErrors.business_type && <small className="au-field-error">{fieldErrors.business_type}</small>}
                    </div>
                  </div>

                  {form.business_type === "Other" && input("Your business type", "custom_type", {
                    required: true,
                    placeholder: "e.g. Bakery, Salon, Hardware store",
                  })}

                  {input("Business address", "business_address", { placeholder: "Enter business address" })}

                  <label className="au-check">
                    <input type="checkbox" name="is_registered" checked={form.is_registered} onChange={change}/>
                    <span>My business is officially registered</span>
                  </label>

                  {form.is_registered && (
                    <div className="au-grid">
                      {input("Registration number", "registration_number", { required: true, placeholder: "Enter registration number" })}
                      <FileField
                        label="Registration document"
                        name="business_registration_document"
                        accept="image/*,.pdf"
                        file={files.business_registration_document}
                        onChange={pickFile}
                        error={fieldErrors.business_registration_document}
                        required={false}
                      />
                    </div>
                  )}
                </fieldset>

                <fieldset className="au-section">
                  <legend>Required documents</legend>
                  <p className="au-hint">Upload clear copies of your documents. Images and PDF are accepted where applicable.</p>
                  <div className="au-grid au-grid-docs">
                    <FileField label="CNIC front" name="cnic_front" accept="image/*,.pdf" file={files.cnic_front} onChange={pickFile} error={fieldErrors.cnic_front}/>
                    <FileField label="CNIC back" name="cnic_back" accept="image/*,.pdf" file={files.cnic_back} onChange={pickFile} error={fieldErrors.cnic_back}/>
                    <FileField label="Passport size photo" name="passport_size_photo" accept="image/*" file={files.passport_size_photo} onChange={pickFile} error={fieldErrors.passport_size_photo}/>
                  </div>
                </fieldset>
              </>
            )}

            {!registered && (
              <button className="lp-btn lp-btn-primary au-submit" disabled={busy}>
                {busy ? "Processing..." : "Create business account"}
              </button>
            )}

            {registered && (
              <button
                type="button"
                className="lp-btn lp-btn-primary au-submit"
                disabled={busy}
                onClick={async () => {
                  setError("");
                  setBusy(true);
                  try {
                    await authApi.resendVerification(verificationEmail);
                    setError("If the account is still unverified, a fresh verification email has been sent.");
                  } catch {
                    setError("Could not resend the verification email. Please try again later.");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {busy ? "Sending..." : "Resend verification email"}
              </button>
            )}

            <p className="au-switch">
              Already have an account? <Link to="/login">Sign in</Link>
            </p>
          </form>
        </div>
      </main>
      <Footer />
    </div>
  );
}