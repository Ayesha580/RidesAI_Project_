import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { publicApi } from "../api/publicApi";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PageCta } from "../components/PageHero";
import "../styles/landing.css";
import "../styles/pages.css";
import "../styles/business.css";

const DISPLAY_LIMIT = 24;

export default function Businesses() {
  const [businesses, setBusinesses] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => {
    let active = true;

    publicApi.businesses()
      .then((response) => {
        if (active) {
          setBusinesses(
            Array.isArray(response.data) ? response.data : []
          );
        }
      })
      .catch(() => {
        if (active) setBusinesses([]);
      })
      .finally(() => {
        if (active) setLoaded(true);
      });

    return () => {
      active = false;
    };
  }, []);

  const recentBusinesses = useMemo(() => {
    return [...businesses]
      .sort((a, b) => {
        const dateA = new Date(
          a.created_at || a.created || a.joined_at || a.updated_at || 0
        ).getTime();

        const dateB = new Date(
          b.created_at || b.created || b.joined_at || b.updated_at || 0
        ).getTime();

        return (
          (Number.isFinite(dateB) ? dateB : 0) -
          (Number.isFinite(dateA) ? dateA : 0)
        );
      })
      .slice(0, DISPLAY_LIMIT);
  }, [businesses]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    if (!q) return recentBusinesses;

    return recentBusinesses.filter((business) =>
      [
        business.name,
        business.business_type,
        business.address,
      ].some((value) =>
        String(value || "").toLowerCase().includes(q)
      )
    );
  }, [recentBusinesses, query]);

  return (
    <div className="lp">
      <Navbar />

      <main className="bd-page">
        <section className="bd-section">
          <div className="bd-container">

            {/* Page heading */}
            <div className="bd-heading">
              <div className="bd-heading-content">
                <span className="bd-eyebrow">
                  <span className="bd-eyebrow-dot" />
                  THE RIDES AI DIRECTORY
                </span>

                <h1>
                  Discover Businesses
                  <span className="bd-heading-period">.</span>
                </h1>

                <p>
                  Explore businesses growing, connecting and operating
                  smarter with Rides AI.
                </p>
              </div>

              <div className="bd-count">
                <div className="bd-count-icon">
                  <BuildingVector />
                </div>

                <div>
                  <span>
                    {loaded ? recentBusinesses.length : "—"}
                  </span>
                  <small>Listed businesses</small>
                </div>
              </div>
            </div>

            {/* Search toolbar */}
            {loaded && recentBusinesses.length > 0 && (
              <div className="bd-toolbar">
                <div className="bd-search">
                  <SearchIcon />

                  <input
                    type="search"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search businesses, industries or locations..."
                    aria-label="Search businesses"
                  />

                  {query && (
                    <button
                      type="button"
                      onClick={() => setQuery("")}
                      aria-label="Clear search"
                      className="bd-clear-search"
                    >
                      ×
                    </button>
                  )}
                </div>

                <div className="bd-results">
                  <span className="bd-results-dot" />
                  Showing <strong>{filtered.length}</strong> of{" "}
                  {recentBusinesses.length} businesses
                </div>
              </div>
            )}

            {/* Loading */}
            {!loaded && (
              <div className="bd-loading">
                <span className="bd-loader" />
                <p>Discovering our business network...</p>
              </div>
            )}

            {/* Empty state */}
            {loaded && businesses.length === 0 && (
              <div className="bd-empty">
                <div className="bd-empty-art">
                  <BuildingVector />
                </div>

                <span className="bd-eyebrow">
                  YOUR OPPORTUNITY STARTS HERE
                </span>

                <h2>Our network is growing.</h2>

                <p>
                  Be among the first businesses to join Rides AI
                  and take your business operations to the next level.
                </p>

                <Link to="/register" className="bd-primary-btn">
                  Join the network
                  <span>↗</span>
                </Link>
              </div>
            )}

            {/* No results */}
            {loaded &&
              businesses.length > 0 &&
              filtered.length === 0 && (
                <div className="bd-no-results">
                  <div className="bd-no-results-icon">
                    <SearchIcon />
                  </div>

                  <h2>No businesses found</h2>

                  <p>
                    We couldn't find a business matching "{query}".
                    Try another name, industry or location.
                  </p>

                  <button
                    type="button"
                    onClick={() => setQuery("")}
                  >
                    Clear search
                  </button>
                </div>
              )}

            {/* Business cards */}
            {loaded && filtered.length > 0 && (
              <div className="bd-grid">
                {filtered.map((business, index) => (
                  <BusinessCard
                    key={business.id || business.name || index}
                    business={business}
                    index={index}
                  />
                ))}
              </div>
            )}

            {/* Bottom note */}
            {loaded && recentBusinesses.length > 0 && (
              <div className="bd-bottom-note">
                <span className="bd-note-star">✦</span>

                <p>
                  Showing most recent
                  businesses in the Rides AI community.
                </p>
              </div>
            )}

          </div>
        </section>

        <PageCta />
      </main>

      <Footer />
    </div>
  );
}

/* Individual business card */
function BusinessCard({ business, index }) {
  const [imageError, setImageError] = useState(false);

  const businessImage =
    business.logo_url ||
    business.logo ||
    business.image_url ||
    business.business_image ||
    business.image ||
    "";

  const verified =
    business.is_verified === true ||
    business.verified === true;

  return (
    <article className="bd-card">

      {/* Gradient identity area */}
      <div className="bd-card-cover">

        <div className="bd-cover-pattern" />

        <div className="bd-card-top">
          <span className="bd-card-number">
            BUSINESS / {String(index + 1).padStart(2, "0")}
          </span>

          {verified ? (
            <span className="bd-verified">
              <CheckIcon />
              Verified
            </span>
          ) : (
            <span className="bd-listed">
              Community
            </span>
          )}
        </div>

        <div className="bd-business-identity">
          <div className="bd-business-logo">
            {businessImage && !imageError ? (
              <img
                src={businessImage}
                alt={`${business.name || "Business"} logo`}
                onError={() => setImageError(true)}
              />
            ) : (
              <BuildingVector />
            )}
          </div>

          <div className="bd-cover-label">
            <span>POWERED BY</span>
            <strong>RIDES AI</strong>
          </div>
        </div>

        <div className="bd-cover-decoration bd-cover-decoration-one" />
        <div className="bd-cover-decoration bd-cover-decoration-two" />
      </div>

      {/* Business details */}
      <div className="bd-card-body">

        <div className="bd-card-info">
          <h3 title={business.name || "Business"}>
            {business.name || "Business"}
          </h3>

          {business.business_type ? (
            <span className="bd-category">
              {business.business_type}
            </span>
          ) : (
            <span className="bd-category bd-category-default">
              Business Member
            </span>
          )}
        </div>

        <div className="bd-card-divider" />

        <div className="bd-address">
          <span className="bd-address-icon">
            <LocationIcon />
          </span>

          <span>
            {business.address || "Location not provided"}
          </span>
        </div>

        <div className="bd-card-footer">
          <div className="bd-member-label">
            <span className="bd-member-dot" />
            <span>RIDES AI MEMBER</span>
          </div>

        </div>

      </div>
    </article>
  );
}

/* Icons */
function BuildingVector() {
  return (
    <svg viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <path
        d="M12 53V23L32 11L52 23V53H12Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <path
        d="M23 53V39C23 34 27 30 32 30C37 30 41 34 41 39V53"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path
        d="M20 25H20.1M32 25H32.1M44 25H44.1"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="M8 53H56"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="10.8" cy="10.8" r="6.8" />
      <path d="m16 16 4.2 4.2" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="m3.5 8 3 3 6-6" />
    </svg>
  );
}

function LocationIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <path d="M16 8.3c0 4.2-6 9-6 9s-6-4.8-6-9a6 6 0 1 1 12 0Z" />
      <circle cx="10" cy="8" r="2" />
    </svg>
  );
}
