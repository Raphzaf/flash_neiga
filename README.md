# Flash Neiga

A full-stack flashcard application for studying and learning, featuring a React frontend and Python FastAPI backend.

## Project Structure

This project consists of two main components:

- **`frontend/`** - React application built with Create React App, using Tailwind CSS and shadcn/ui components
- **`backend/`** - Python FastAPI server for API endpoints and data management

## Prerequisites

- **Node.js** 18.x or higher (for frontend)
- **Python** 3.9 or higher (for backend)
- **npm** or **yarn** (for frontend package management)
- **pip** (for Python package management)

## Local Development

### Frontend Development

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm start
   ```

   The frontend will run at [http://localhost:3000](http://localhost:3000)

4. Build for production:
   ```bash
   npm run build
   ```

### Backend Development

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the FastAPI server:
   ```bash
   uvicorn server:app --reload --port 8000
   ```

   The backend API will run at [http://localhost:8000](http://localhost:8000)

### Full Stack Development

To run both frontend and backend together:

1. Start the backend server (as described above)
2. In a separate terminal, start the frontend development server
3. The frontend is configured to proxy API requests to the backend at `http://localhost:8000`

## Deployment

### Netlify Deployment (Frontend Only)

The frontend is configured for easy deployment to Netlify. The repository includes a `netlify.toml` configuration file that:

- Sets the base directory to `frontend`
- Configures the build command as `npm run build`
- Publishes the `build` directory
- Uses Node.js version 18

#### Deploy to Netlify:

1. **Connect your repository** to Netlify:
   - Log in to [Netlify](https://www.netlify.com)
   - Click "Add new site" → "Import an existing project"
   - Connect to your Git provider and select this repository

2. **Deploy settings** (automatically configured via `netlify.toml`):
   - Base directory: `frontend`
   - Build command: `npm run build`
   - Publish directory: `frontend/build`
   - Node version: 18

3. **Deploy**: Netlify will automatically build and deploy your site. Subsequent pushes to your main branch will trigger automatic deployments.

#### Manual Deployment:

Alternatively, you can deploy manually using the Netlify CLI:

```bash
cd frontend
npm install -g netlify-cli
netlify deploy --prod
```

### Backend Deployment

The Python backend can be deployed to various platforms:

- **Heroku**: Using a `Procfile` with `web: uvicorn backend.server:app --host 0.0.0.0 --port $PORT`
- **Railway**: Auto-detects FastAPI and deploys with minimal configuration
- **AWS EC2/Lambda**: Using serverless frameworks or traditional hosting
- **DigitalOcean App Platform**: Supports Python applications natively

Ensure you set up environment variables and configure CORS settings in the backend to allow requests from your deployed frontend domain.

## Configuration

### Frontend Configuration

The frontend uses:
- **CRACO** (Create React App Configuration Override) for customizing the build configuration
- **Tailwind CSS** for styling
- **React Router** for navigation
- **shadcn/ui** components for UI elements

Configuration files:
- `frontend/craco.config.js` - Build configuration overrides
- `frontend/tailwind.config.js` - Tailwind CSS configuration
- `frontend/.env` - Environment variables

### Backend Configuration

The backend requires:
- Database connection settings (SQLAlchemy)
- API keys (if using external services)
- CORS configuration for frontend access

## Technologies Used

### Frontend
- React 19
- React Router DOM
- Tailwind CSS
- shadcn/ui (Radix UI components)
- Axios for API calls
- CRACO for build customization

### Backend
- FastAPI
- SQLAlchemy
- Uvicorn
- Pydantic
- JWT authentication
- Bcrypt for password hashing

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is private and proprietary.
