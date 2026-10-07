import { Outlet } from 'react-router-dom';
import Navbar from './Navbar';
import Footer from './Footer';

/** Page frame shared by every route: navigation bar, the page, footer. */
export default function Layout({ footer = true }) {
    return (
        <>
            <Navbar />
            <Outlet />
            {footer && <Footer />}
        </>
    );
}
