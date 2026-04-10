import { Link } from "react-router-dom";

function Navbar() {
  return (
    <nav className="navbar">
      <Link to="/" className="navbar__logo">
        Video Games Bourse
      </Link>
      <ul className="navbar__links">
        <li>
          <Link to="/">Accueil</Link>
        </li>
        <li>
          <Link to="/games">Catalogue</Link>
        </li>
        <li>
          <Link to="/opportunities">Bonnes affaires</Link>
        </li>
      </ul>
    </nav>
  );
}

export default Navbar;
