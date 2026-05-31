import Icon from "@/components/ui/Icon";

export default function EmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="text-center select-none">
        <Icon name="psychology" size={64} className="text-primary/30 mb-4 block mx-auto" />
        <p className="font-headline-md text-headline-md text-on-surface-variant mb-2">
          Your extended cognitive field.
        </p>
        <p className="font-metadata text-metadata text-outline">
          Start a conversation to capture and retrieve your memories.
        </p>
      </div>
    </div>
  );
}
