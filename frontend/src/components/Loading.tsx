export default function Loading() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-background">
      <div className="flex flex-col items-center gap-4">
        <div className="relative">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-primary/20 border-t-primary"></div>
          <div className="absolute inset-0 animate-ping rounded-full h-12 w-12 border-2 border-primary/30"></div>
        </div>
        <p className="text-muted-foreground text-sm font-medium">Loading...</p>
      </div>
    </div>
  )
}

