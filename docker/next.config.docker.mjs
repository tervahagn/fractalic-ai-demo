/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true, // Enable React strict mode for development
  async rewrites() {
    // Use environment variable for backend URL, default to localhost for Docker
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000';
    
    return [
      {
        source: '/list_directory',
        destination: `${backendUrl}/list_directory`,
      },
      {
        source: '/branches_and_commits',
        destination: `${backendUrl}/branches_and_commits`,
      },
      {
        source: '/get_file_content_disk',
        destination: `${backendUrl}/get_file_content_disk`,
      },
      {
        source: '/create_file',
        destination: `${backendUrl}/create_file`,
      },
      {
        source: '/create_folder',
        destination: `${backendUrl}/create_folder`,
      },
      {
        source: '/get_file_content',
        destination: `${backendUrl}/get_file_content`,
      },
      {
        source: '/save_file',
        destination: `${backendUrl}/save_file`,
      },
      {
        source: '/delete_item',
        destination: `${backendUrl}/delete_item`,
      },
      {
        source: '/rename_item',
        destination: `${backendUrl}/rename_item`,
      },
      {
        source: '/load_settings',
        destination: `${backendUrl}/load_settings`,
      },
      {
        source: '/save_settings',
        destination: `${backendUrl}/save_settings`,
      },
    ];
  },
};

export default nextConfig;
