FROM nginx:alpine

# Copy the website files to the nginx web root
COPY llms.txt /usr/share/nginx/html/
COPY sitemap.xml /usr/share/nginx/html/

# Copy any other static files (if they exist)
# COPY . /usr/share/nginx/html/

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]