<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Create binary_markets table for Polymarket binary options.
     *
     * Stores metadata about binary option markets:
     * - Market identification (symbol, market_id)
     * - Market details (question, description, category)
     * - Lifecycle (end_date, status, resolution)
     */
    public function up(): void
    {
        Schema::create('binary_markets', function (Blueprint $table) {
            $table->id();
            $table->foreignId('symbol_id')->constrained('symbols')->onDelete('cascade');

            // Polymarket identifiers
            $table->string('market_id', 100)->unique()->comment('Polymarket internal market ID');

            // Market details
            $table->text('question')->comment('Market question (e.g., "Will Trump win 2024?")');
            $table->text('description')->nullable()->comment('Full market description and resolution criteria');
            $table->string('category', 50)->nullable()->comment('Category: politics, sports, crypto, etc.');

            // Lifecycle management
            $table->timestampTz('end_date')->comment('Market resolution deadline');
            $table->string('status', 20)->default('active')->comment('active, resolved, closed, cancelled');
            $table->string('resolution', 10)->nullable()->comment('yes, no, null (after resolution)');

            // Timestamps
            $table->timestampsTz();

            // Indexes for performance
            $table->index('symbol_id');
            $table->index('status');
            $table->index('end_date');
            $table->index('category');
            $table->index(['status', 'end_date'], 'idx_binary_markets_active');
        });
    }

    /**
     * Reverse the migration.
     */
    public function down(): void
    {
        Schema::dropIfExists('binary_markets');
    }
};
