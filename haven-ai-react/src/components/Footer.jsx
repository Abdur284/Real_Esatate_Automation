import { Link } from 'react-router-dom';

export default function Footer() {
    return (
        <footer>
            <div className="footer-inner">
                <div className="footer-brand">
                    <Link to="/" className="logo">HAVEN<span>.</span>AI</Link>
                    <p>An AI-powered platform that transforms how you design, plan, visualize, and find your perfect home.</p>
                </div>
                <div className="footer-col">
                    <h5>Design Tools</h5>
                    <ul>
                        <li><Link to="/2d-design">2D Floor Plans</Link></li>
                        <li><Link to="/3d-design">3D Visualization</Link></li>
                        <li><Link to="/interior-design">Interior Design</Link></li>
                        <li><Link to="/cost-estimation">Cost Estimation</Link></li>
                    </ul>
                </div>
                <div className="footer-col">
                    <h5>Properties</h5>
                    <ul>
                        <li><Link to="/properties">Browse Listings</Link></li>
                        <li><Link to="/properties">For Sale</Link></li>
                        <li><Link to="/properties">For Rent</Link></li>
                        <li><Link to="/properties">List a Property</Link></li>
                    </ul>
                </div>
                <div className="footer-col">
                    <h5>Company</h5>
                    <ul>
                        <li><a href="#">About</a></li>
                        <li><a href="#">Contact</a></li>
                        <li><a href="#">Privacy Policy</a></li>
                        <li><a href="#">Terms of Use</a></li>
                    </ul>
                </div>
            </div>
            <div className="footer-bottom">
                <span>© 2026 HAVEN.AI. All rights reserved.</span>
            </div>
        </footer>
    );
}
