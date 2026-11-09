import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import Footer from "../components/Footer";
import { PageCta } from "../components/PageHero";
import {
  STEP_DETAILS,
  ORDER_FLOW,
  CHANNELS,
} from "../data/siteContent";

import "../styles/landing.css";
import "../styles/pages.css";
import "../styles/howitwork.css";

export default function HowItWorks() {
  return (
    <div className="lp hiw-page">
      <Navbar />

      <main>
        {/* INTRODUCTION */}
        <section className="hiw-intro">
          <div className="hiw-container">
            <div className="hiw-intro-content">
              <span className="hiw-eyebrow">
                <span className="hiw-eyebrow-dot" />
                HOW RIDES AI WORKS
              </span>

              <h1>
                From setup to
                <br />
                <span>smarter business operations.</span>
              </h1>

              <p>
                Getting started is simple. Set up your business,
                configure your AI agent, connect your customers
                and let Rides AI handle the everyday interactions.
              </p>

              <div className="hiw-intro-actions">
                <Link
                  to="/register"
                  className="hiw-primary-btn"
                >
                  Register Your Business
                  <span>↗</span>
                </Link>

                <span className="hiw-intro-note">
                  Four simple steps to get started
                </span>
              </div>
            </div>

            <div className="hiw-intro-visual">
              <div className="hiw-visual-card">
                <div className="hiw-visual-top">
                  <span className="hiw-status-dot" />
                  <span>YOUR BUSINESS, CONNECTED</span>
                </div>

                <div className="hiw-visual-center">
                  <div className="hiw-visual-orbit">
                    <div className="hiw-visual-logo">
                      <svg
                        viewBox="0 0 48 48"
                        fill="none"
                        aria-hidden="true"
                      >
                        <path
                          d="M24 5L41 15V33L24 43L7 33V15L24 5Z"
                          stroke="currentColor"
                          strokeWidth="2"
                        />
                        <path
                          d="M16 24L22 30L33 18"
                          stroke="currentColor"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </div>
                  </div>

                  <h3>Rides AI</h3>
                  <p>Your AI-powered business manager</p>
                </div>

                <div className="hiw-visual-bottom">
                  <div>
                    <span className="hiw-mini-icon">01</span>
                    <strong>Business setup</strong>
                  </div>

                  <div>
                    <span className="hiw-mini-icon">02</span>
                    <strong>AI configuration</strong>
                  </div>

                  <div>
                    <span className="hiw-mini-icon">03</span>
                    <strong>Customer connections</strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SETUP STEPS */}
        <section className="hiw-section hiw-steps-section">
          <div className="hiw-container">
            <div className="hiw-section-heading">
              <span className="hiw-eyebrow">
                THE GETTING STARTED PROCESS
              </span>

              <h2>
                Four steps to get
                <br />
                <span>your business running.</span>
              </h2>

              <p>
                Everything you need to get your AI agent ready
                for real customer interactions.
              </p>
            </div>

            <div className="hiw-steps-grid">
              {STEP_DETAILS.map((step, index) => (
                <article
                  className="hiw-step-card"
                  key={step.number}
                >
                  <div className="hiw-step-top">
                    <span className="hiw-step-number">
                      {String(step.number).padStart(2, "0")}
                    </span>

                    <span className="hiw-step-label">
                      STEP {String(index + 1).padStart(2, "0")}
                    </span>
                  </div>

                  <div className="hiw-step-line" />

                  <h3>{step.title}</h3>

                  <p className="hiw-step-description">
                    {step.text}
                  </p>

                  <ul className="hiw-check-list">
                    {step.points.map((point) => (
                      <li key={point}>
                        <span className="hiw-check-icon">
                          ✓
                        </span>
                        {point}
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ORDER FLOW */}
        <section className="hiw-section hiw-flow-section">
          <div className="hiw-container">
            <div className="hiw-flow-layout">
              <div className="hiw-flow-intro">
                <span className="hiw-eyebrow">
                  SEE IT IN ACTION
                </span>

                <h2>
                  One customer order,
                  <br />
                  <span>handled step by step.</span>
                </h2>

                <p>
                  From the first customer message to order
                  confirmation, Rides AI manages the interaction
                  while keeping the customer informed.
                </p>

                <div className="hiw-flow-highlight">
                  <span className="hiw-highlight-icon">✓</span>

                  <div>
                    <strong>Customer confirmation comes first</strong>
                    <p>
                      The agent never places an order without
                      the customer's confirmation.
                    </p>
                  </div>
                </div>
              </div>

              <div className="hiw-flow-card">
                <div className="hiw-flow-card-header">
                  <div>
                    <span className="hiw-flow-overline">
                      ORDER JOURNEY
                    </span>
                    <h3>How an order moves</h3>
                  </div>

                  <span className="hiw-flow-count">
                    {String(ORDER_FLOW.length).padStart(2, "0")} STEPS
                  </span>
                </div>

                <ol className="hiw-flow-list">
                  {ORDER_FLOW.map((item, index) => (
                    <li key={item}>
                      <span className="hiw-flow-number">
                        {String(index + 1).padStart(2, "0")}
                      </span>

                      <div className="hiw-flow-item-content">
                        <span className="hiw-flow-item-title">
                          {item}
                        </span>
                      </div>

                      {index === ORDER_FLOW.length - 1 && (
                        <span className="hiw-flow-complete">
                          ✓
                        </span>
                      )}
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </div>
        </section>

        {/* CUSTOMER CHANNELS */}
        <section className="hiw-section hiw-channels-section">
          <div className="hiw-container">
            <div className="hiw-section-heading">
              <span className="hiw-eyebrow">
                CUSTOMER CONNECTIONS
              </span>

              <h2>
                Meet your customers
                <br />
                <span>where they already are.</span>
              </h2>

              <p>
                Give customers convenient ways to interact
                with your AI agent through your preferred channels.
              </p>
            </div>

            <div className="hiw-channel-grid">
              {CHANNELS.map((channel, index) => (
                <article
                  className="hiw-channel-card"
                  key={channel.title}
                >
                  <div className="hiw-channel-top">
                    <div className="hiw-channel-icon">
                      {channel.icon}
                    </div>

                    <span className="hiw-channel-number">
                      0{index + 1}
                    </span>
                  </div>

                  <h3>{channel.title}</h3>

                  <p>{channel.text}</p>

                  <div className="hiw-channel-footer">
                    <span>RIDES AI INTEGRATION</span>
                    <span>↗</span>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <PageCta />
      </main>

      <Footer />
    </div>
  );
}