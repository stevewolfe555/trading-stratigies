<div class="space-y-4" wire:poll.15s>
    <h3 class="font-semibold text-lg">Recent Signals</h3>
    <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
            <thead>
            <tr class="text-left border-b">
                <th class="py-2 pr-4">Time</th>
                <th class="py-2 pr-4">Symbol</th>
                <th class="py-2 pr-4">Strategy</th>
                <th class="py-2 pr-4">Type</th>
                <th class="py-2 pr-4">Details</th>
            </tr>
            </thead>
            <tbody>
            @forelse($rows as $r)
                <tr class="border-b">
                    <td class="py-2 pr-4 text-gray-600">{{ $r['time'] }}</td>
                    <td class="py-2 pr-4 font-semibold">{{ $r['symbol'] }}</td>
                    <td class="py-2 pr-4">{{ $r['strategy'] }}</td>
                    <td class="py-2 pr-4">{{ $r['type'] }}</td>
                    <td class="py-2 pr-4 text-gray-600 break-all">{{ $r['details'] }}</td>
                </tr>
            @empty
                <tr>
                    <td colspan="5" class="py-4 text-gray-500">No signals yet.</td>
                </tr>
            @endforelse
            </tbody>
        </table>
    </div>
</div>
